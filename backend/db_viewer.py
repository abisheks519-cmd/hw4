"""Refresh campus_customs_db.html, the browsable snapshot of campus_customs.db.

The viewer page keeps a copy of the data inside it, so it doesn't change when the database
does (e.g. after someone creates an account on the website). Run this to rebuild that copy
from the live database:

    cd backend
    python db_viewer.py

It only reads the database, and it only replaces the data block and the "refreshed" note in
the page; the page's layout and code stay as they are.
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from db import DB_PATH, ROOT

VIEWER = ROOT / "campus_customs_db.html"


def snapshot() -> dict:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = lambda sql: [dict(r) for r in con.execute(sql)]
    try:
        cat = rows("SELECT product_id, name, garment_type, description, colors, search_tags, image_file_path, price FROM catalogue ORDER BY name")
        for c in cat:
            c["colors"] = json.loads(c["colors"])
            c["search_tags"] = json.loads(c["search_tags"])
        tables = [r["name"] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
        return {
            "cat": cat,
            "inv": rows("SELECT id, product_id, size, quantity FROM inventory ORDER BY id"),
            "users": rows("SELECT id, name, first_name, last_name, email, created_at, password_hash FROM users ORDER BY id"),
            "msgs": rows("SELECT id, user_id, role, content, products_json IS NOT NULL AS has_products, created_at "
                         "FROM chat_messages ORDER BY user_id, id"),
            "schema": {t: rows(f"PRAGMA table_info({t})") for t in tables},
            "counts": {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables},
        }
    finally:
        con.close()


def refresh() -> dict:
    html = VIEWER.read_text(encoding="utf-8")
    data = snapshot()
    # "</" is escaped so text from the database (e.g. a chat message) can't end the <script> early.
    block = "const D = " + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + ";"
    html, found = re.subn(r"^const D = .*;$", lambda _: block, html, count=1, flags=re.M)
    if not found:
        raise SystemExit("Couldn't find the data block in campus_customs_db.html.")
    stamp = datetime.now().strftime("%b %-d, %Y at %-I:%M %p")
    html = re.sub(r"<p>Read-only snapshot of <code>campus_customs.db</code>.*?</p>",
                  f"<p>Read-only snapshot of <code>campus_customs.db</code> · refreshed {stamp}</p>", html, count=1)
    VIEWER.write_text(html, encoding="utf-8")
    return data["counts"]


if __name__ == "__main__":
    counts = refresh()
    print(f"Refreshed {VIEWER.name}: " + ", ".join(f"{t} {n}" for t, n in counts.items()))
