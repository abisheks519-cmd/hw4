"""Append-only audit trail of the shop assistant's agent loop: output/audit_trail.json.

Every chat message the assistant handles adds entries like:

    run_start       a new run: run id, mode (llm or keyword-fallback), model, shopper (id only), page, message
    model_response  one model step: stop reason, tool calls requested, token usage
    tool_call       a tool the agent called, with short arguments
    tool_result     what the tool returned (shortened)
    retry           a tool error or output check that sent the model back to try again
    error           the model/network failed, or a loop limit was hit (the fallback answers instead)
    run_end         the outcome: stop reason, reply (shortened), product cards shown, totals, duration

The file is a JSON array that is only ever appended to. A new entry is written in place of the
closing "]" (so existing entries are never rewritten), and the file is never cleared between
runs or server restarts. A lock keeps two requests from writing at the same time.

Privacy: shoppers are recorded by account id only (never email or password), long digit runs
(card or phone numbers) and email addresses in messages are masked, and every text field is
shortened.
"""

import fcntl
import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic_core import to_jsonable_python

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
SHORT = 200  # characters kept from any message, argument, or result
_lock = threading.Lock()

CARD_LIKE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")  # card-length digit runs
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def short(value, limit: int = SHORT) -> str:
    """A one-line, masked, shortened text version of any value."""
    if not isinstance(value, str):
        try:  # tool results are Pydantic models; turn them into plain JSON first
            value = json.dumps(to_jsonable_python(value, fallback=str), ensure_ascii=False)
        except (TypeError, ValueError):
            value = str(value)
    value = EMAIL.sub("[email]", CARD_LIKE.sub("[number]", value))
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def append(entry: dict) -> None:
    """Add one entry to the end of the trail. Never rewrites or removes earlier entries."""
    line = json.dumps(entry, ensure_ascii=False, default=str)
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_PATH, "a+b") as f:  # append mode: every write lands at the end of the file
            fcntl.flock(f, fcntl.LOCK_EX)  # also guards against a second server process
            try:
                closing = _last_char_at(f, f.seek(0, 2))
                if closing is None:  # new file
                    f.write(f"[\n{line}\n]\n".encode())
                elif closing[0] == b"]":
                    # Replace only the closing "]" with ",<entry>]". Earlier entries are untouched.
                    before = _last_char_at(f, closing[1])
                    sep = "" if before is None or before[0] == b"[" else ","
                    f.truncate(before[1] + 1 if before else 0)
                    f.write(f"{sep}\n{line}\n]\n".encode())
                else:  # unexpected ending (e.g. edited by hand): keep everything, just add on
                    f.write(f",\n{line}\n]\n".encode())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def _last_char_at(f, end: int):
    """The last non-whitespace byte before position `end`, and its position (None if there isn't one)."""
    pos = end
    while pos > 0:
        f.seek(pos - 1)
        ch = f.read(1)
        if ch not in b" \n\r\t":
            return ch, pos - 1
        pos -= 1
    return None


class AuditRun:
    """Records one run of the agent loop. Logging problems never interrupt the chat."""

    def __init__(self, mode: str, model: str | None, customer=None, page=None, message: str = ""):
        self.run_id = uuid.uuid4().hex[:12]
        self.started = time.monotonic()
        self.step = 0
        self.log(
            "run_start", mode=mode, model=model,
            shopper=f"user {customer.user_id}" if customer else "guest",
            page=(f"{page.page} {page.path}" if page else None), message=short(message),
        )

    def log(self, event: str, **fields) -> None:
        entry = {"time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "run_id": self.run_id,
                 "event": event}
        entry.update({k: v for k, v in fields.items() if v is not None})
        try:
            append(entry)
        except OSError:
            pass

    def elapsed_ms(self) -> int:
        return round((time.monotonic() - self.started) * 1000)
