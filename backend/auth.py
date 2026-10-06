"""Account creation and login for Campus Customs.

Passwords are never stored in plain text. Each password is run through PBKDF2-HMAC-SHA256
with a random per-user salt and many iterations, and only the resulting hash is saved.
The stored value looks like:

    pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>

Because the salt is random and unique per user, two people with the same password get
different hashes, and the hash cannot be reversed back into the password.

After signing up or logging in, the shopper gets a session: a random token sent back as an
HttpOnly cookie (page scripts can't read it). Only a SHA-256 hash of the token is stored, in the
user_sessions table, so a copy of the database can't be used to take over a session. The chat
uses the session to know which shopper is talking and whose history to load.
"""

import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from models import CustomerContext
from validation import check_email, check_name, check_password

DB_PATH = Path(__file__).resolve().parent.parent / "campus_customs.db"
ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 260_000  # Work factor: high enough to slow brute-force attacks on the hashes.
SESSION_COOKIE = "cc_session"
SESSION_DAYS = 30

router = APIRouter(prefix="/api/auth", tags=["auth"])


def hash_password(password: str) -> str:
    """Turn a plain password into a salted PBKDF2-SHA256 hash string for storage."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"{ALGORITHM}${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a plain password against a stored hash without ever un-hashing it."""
    parts = stored.split("$")
    try:
        if len(parts) == 4:
            _, iterations, salt_hex, digest_hex = parts
            salt = bytes.fromhex(salt_hex)
            iters = int(iterations)
        elif len(parts) == 3:
            # Legacy seed accounts stored as pbkdf2_sha256$<salt>$<hash>.
            _, salt_hex, digest_hex = parts
            salt = bytes.fromhex(salt_hex)
            iters = ITERATIONS
        else:
            return False
    except ValueError:
        return False
    computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    # Constant-time comparison so an attacker can't learn the hash from timing.
    return hmac.compare_digest(computed.hex(), digest_hex)


def writable_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ---- Sessions ---------------------------------------------------------------------

def init_session_storage() -> None:
    """Create the user_sessions table if it's missing. Safe to run every time the API starts."""
    con = writable_connection()
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);
            """
        )
        con.commit()
    finally:
        con.close()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def start_session(response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    con = writable_connection()
    try:
        con.execute("DELETE FROM user_sessions WHERE expires_at <= datetime('now')")
        con.execute(
            "INSERT INTO user_sessions (token_hash, user_id, expires_at) VALUES (?, ?, datetime('now', ?))",
            (_token_hash(token), user_id, f"+{SESSION_DAYS} days"),
        )
        con.commit()
    finally:
        con.close()
    # HttpOnly: page scripts can't read it. SameSite=Lax: other sites can't send it with their requests.
    # (Add secure=True when the site is served over HTTPS.)
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", path="/")


def current_user_row(request: Request) -> sqlite3.Row | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    con = writable_connection()
    try:
        return con.execute(
            "SELECT u.* FROM user_sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > datetime('now')",
            (_token_hash(token),),
        ).fetchone()
    finally:
        con.close()


def get_customer(request: Request) -> CustomerContext | None:
    """FastAPI dependency: the signed-in shopper for this request, or None for a guest."""
    row = current_user_row(request)
    if row is None:
        return None
    return CustomerContext(
        user_id=row["id"], first_name=row["first_name"], last_name=row["last_name"],
        name=row["name"], email=row["email"], member_since=str(row["created_at"])[:10],
    )


def require_customer(request: Request) -> CustomerContext:
    """FastAPI dependency for routes that need a signed-in shopper."""
    customer = get_customer(request)
    if customer is None:
        raise HTTPException(status_code=401, detail="Please log in to see your saved chats.")
    return customer


# ---- Requests and responses ------------------------------------------------------

class SignupRequest(BaseModel):
    """Checked with the shared rules in validation.py; each bad field gets its own message."""

    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str

    @field_validator("first_name", "last_name")
    @classmethod
    def valid_name(cls, v: str, info) -> str:
        return check_name(v, "First name" if info.field_name == "first_name" else "Last name")

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        return check_email(v)

    @field_validator("password")
    @classmethod
    def strong_enough(cls, v: str) -> str:
        return check_password(v)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if not v:
            raise ValueError("Please confirm your password.")
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords don't match.")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        return check_email(v)

    @field_validator("password")
    @classmethod
    def present(cls, v: str) -> str:
        if not v:
            raise ValueError("Password is required.")
        return v


class UserOut(BaseModel):
    id: int
    first_name: str | None
    last_name: str | None
    name: str
    email: str
    is_admin: bool = False  # admins can open the analytics dashboard


def to_user_out(row: sqlite3.Row) -> UserOut:
    return UserOut(
        id=row["id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        name=row["name"],
        email=row["email"],
        is_admin=bool(row["is_admin"]) if "is_admin" in row.keys() else False,
    )


def _carry_over_cart(request: Request, user_id: int) -> None:
    # A guest's cart joins the account's saved cart when they sign in.
    from shop import merge_visitor_cart

    merge_visitor_cart(getattr(request.state, "visitor_id", None), user_id)


# ---- Routes ----------------------------------------------------------------------

@router.post("/signup", response_model=UserOut, status_code=201)
def signup(req: SignupRequest, request: Request, response: Response):
    email = req.email
    full_name = f"{req.first_name} {req.last_name}"
    password_hash = hash_password(req.password)

    con = writable_connection()
    try:
        cur = con.execute(
            "INSERT INTO users (name, first_name, last_name, email, password_hash) VALUES (?, ?, ?, ?, ?)",
            (full_name, req.first_name, req.last_name, email, password_hash),
        )
        con.commit()
        row = con.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        # The users table has a UNIQUE constraint on email.
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    finally:
        con.close()
    start_session(response, row["id"])
    _carry_over_cart(request, row["id"])
    return to_user_out(row)


@router.post("/login", response_model=UserOut)
def login(req: LoginRequest, request: Request, response: Response):
    email = req.email
    con = writable_connection()
    try:
        row = con.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    finally:
        con.close()

    # Same error whether the email is unknown or the password is wrong, so an
    # attacker can't tell which emails have accounts.
    if row is None or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    start_session(response, row["id"])
    _carry_over_cart(request, row["id"])
    return to_user_out(row)


@router.get("/me", response_model=UserOut | None)
def me(request: Request):
    """The signed-in shopper (from their session cookie), or null for a guest."""
    row = current_user_row(request)
    return to_user_out(row) if row else None


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        con = writable_connection()
        try:
            con.execute("DELETE FROM user_sessions WHERE token_hash = ?", (_token_hash(token),))
            con.commit()
        finally:
            con.close()
    response.delete_cookie(SESSION_COOKIE, path="/")
