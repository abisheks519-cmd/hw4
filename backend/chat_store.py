"""Saved chat history for signed-in shoppers.

Tables (in campus_customs.db):
  chat_conversations  one row per conversation: id, user_id, title, created_at, updated_at
  chat_messages       one row per message (existing table): id, user_id, role, content,
                      products_json, created_at, plus conversation_id and results_title

Guests' chats are never written here. Every read and write takes the signed-in user's id,
so a shopper can only ever reach their own conversations.
"""

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

from db import DB_PATH, cached_products, connect
from models import ChatResponse, ChatTurn, ConversationDetail, ConversationSummary, ProductCard, StoredMessage

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_chat_conversations_user ON chat_conversations(user_id, updated_at);
"""

# Older messages (saved before conversations existed) more than this far apart start a new conversation.
LEGACY_GAP = timedelta(minutes=30)
GREETINGS = {"hi", "hey", "hello", "yo", "sup", "hiya", "howdy", "hey there", "hi there",
             "good morning", "good afternoon", "good evening"}


@contextmanager
def connect_rw():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def title_for(user_messages: list[str]) -> str:
    """A conversation's title: its first real question (skipping greetings like "yo"), tidied and shortened."""
    candidates = [m for m in user_messages if m.strip()]
    if not candidates:
        return "New chat"
    first = next((m for m in candidates if re.sub(r"[^a-z ]", "", m.lower()).strip() not in GREETINGS), candidates[0])
    clean = re.sub(r"\s+", " ", first.strip())
    title = clean[0].upper() + clean[1:]
    return title if len(title) <= 42 else title[:41].rstrip() + "…"


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


# ---- Setup ------------------------------------------------------------------------

def init_chat_storage() -> None:
    """Create the chat tables and columns if they're missing, and group older messages into
    conversations. Safe to run every time the API starts."""
    with connect_rw() as con:
        con.executescript(SCHEMA)
        columns = {r["name"] for r in con.execute("PRAGMA table_info(chat_messages)")}
        if "conversation_id" not in columns:
            con.execute("ALTER TABLE chat_messages ADD COLUMN conversation_id INTEGER REFERENCES chat_conversations(id)")
        if "results_title" not in columns:
            con.execute("ALTER TABLE chat_messages ADD COLUMN results_title TEXT")
        con.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation ON chat_messages(conversation_id, id)")
        _group_legacy_messages(con)


def _group_legacy_messages(con: sqlite3.Connection) -> None:
    rows = con.execute(
        "SELECT id, user_id, role, content, created_at FROM chat_messages "
        "WHERE conversation_id IS NULL ORDER BY user_id, created_at, id"
    ).fetchall()
    groups: list[list[sqlite3.Row]] = []
    for r in rows:
        last = groups[-1][-1] if groups else None
        if last is None or r["user_id"] != last["user_id"] or _ts(r["created_at"]) - _ts(last["created_at"]) > LEGACY_GAP:
            groups.append([])
        groups[-1].append(r)
    for group in groups:
        title = title_for([r["content"] for r in group if r["role"] == "user"])
        cur = con.execute(
            "INSERT INTO chat_conversations (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (group[0]["user_id"], title, group[0]["created_at"], group[-1]["created_at"]),
        )
        con.executemany("UPDATE chat_messages SET conversation_id = ? WHERE id = ?", [(cur.lastrowid, r["id"]) for r in group])


# ---- Reading --------------------------------------------------------------------

def list_conversations(user_id: int, limit: int = 50) -> list[ConversationSummary]:
    with connect() as con:
        rows = con.execute(
            "SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(m.id) AS message_count "
            "FROM chat_conversations c LEFT JOIN chat_messages m ON m.conversation_id = c.id "
            "WHERE c.user_id = ? GROUP BY c.id ORDER BY c.updated_at DESC, c.id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [ConversationSummary(**dict(r)) for r in rows]


def get_conversation(user_id: int, conversation_id: int) -> ConversationDetail | None:
    with connect() as con:
        conv = con.execute(
            "SELECT id, title, created_at, updated_at FROM chat_conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        if conv is None:
            return None
        rows = con.execute(
            "SELECT role, content, products_json, results_title, created_at FROM chat_messages "
            "WHERE conversation_id = ? AND user_id = ? ORDER BY id",
            (conversation_id, user_id),
        ).fetchall()
    # Cards are rebuilt from today's catalogue, so reopened chats show current prices and stock.
    catalogue = {p["product_id"]: p for p in cached_products()}
    messages = [
        StoredMessage(
            role=r["role"], content=r["content"], results_title=r["results_title"], created_at=r["created_at"],
            products=[ProductCard(**catalogue[i]) for i in _product_ids(r["products_json"]) if i in catalogue],
        )
        for r in rows
        if r["role"] in ("user", "assistant")
    ]
    return ConversationDetail(**dict(conv), message_count=len(messages), messages=messages)


def _product_ids(products_json: str | None) -> list[str]:
    try:
        items = json.loads(products_json or "[]")
    except json.JSONDecodeError:
        return []
    return [p["product_id"] for p in items if isinstance(p, dict) and "product_id" in p]


def history_turns(user_id: int, conversation_id: int, limit: int = 12) -> list[ChatTurn] | None:
    """The latest turns of one of this shopper's conversations, for the agent. None if it isn't theirs."""
    with connect() as con:
        owned = con.execute(
            "SELECT 1 FROM chat_conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id)
        ).fetchone()
        if owned is None:
            return None
        rows = con.execute(
            "SELECT role, content FROM chat_messages WHERE conversation_id = ? AND user_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, user_id, limit),
        ).fetchall()
    return [ChatTurn(role=r["role"], content=r["content"]) for r in reversed(rows) if r["role"] in ("user", "assistant")]


# ---- Writing --------------------------------------------------------------------

def save_exchange(user_id: int, conversation_id: int | None, message: str, response: ChatResponse) -> tuple[int, str]:
    """Store one question and the assistant's reply. Starts a new conversation when conversation_id is None."""
    products_json = json.dumps([p.model_dump() for p in response.products]) if response.products else None
    with connect_rw() as con:
        if conversation_id is None:
            conversation_id = con.execute(
                "INSERT INTO chat_conversations (user_id, title) VALUES (?, ?)", (user_id, title_for([message]))
            ).lastrowid
        con.execute(
            "INSERT INTO chat_messages (user_id, conversation_id, role, content) VALUES (?, ?, 'user', ?)",
            (user_id, conversation_id, message),
        )
        con.execute(
            "INSERT INTO chat_messages (user_id, conversation_id, role, content, products_json, results_title) "
            "VALUES (?, ?, 'assistant', ?, ?, ?)",
            (user_id, conversation_id, response.reply, products_json, response.results_title),
        )
        questions = [r["content"] for r in con.execute(
            "SELECT content FROM chat_messages WHERE conversation_id = ? AND role = 'user' ORDER BY id", (conversation_id,)
        )]
        title = title_for(questions)
        con.execute(
            "UPDATE chat_conversations SET title = ?, updated_at = datetime('now') WHERE id = ? AND user_id = ?",
            (title, conversation_id, user_id),
        )
    return conversation_id, title


def delete_conversation(user_id: int, conversation_id: int) -> bool:
    with connect_rw() as con:
        owned = con.execute(
            "SELECT 1 FROM chat_conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id)
        ).fetchone()
        if owned is None:
            return False
        con.execute("DELETE FROM chat_messages WHERE conversation_id = ? AND user_id = ?", (conversation_id, user_id))
        con.execute("DELETE FROM chat_conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
    return True
