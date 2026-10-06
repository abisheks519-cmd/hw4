"""Shopping cart, checkout, and orders.

Tables (in campus_customs.db):
  carts        one per signed-in shopper (user_id) or per guest browser (visitor_id)
  cart_items   what's in each cart: product, size, quantity
  orders       one row per checkout: contact, shipping address, card brand + last 4, totals
  order_items  the products, sizes, quantities, and prices in each order

Signed-in shoppers' carts are tied to their account, so the cart is still there after they log
out and back in (on any device). A guest's cart is tied to an anonymous browser id cookie; when
they log in, it is merged into their account's cart.

Prices and stock are always read from the catalogue when a cart is shown, and checked again at
checkout, so a cart can never be sold at a stale price or beyond the stock on hand. Card numbers
are format-checked (see validation.py) but never charged or stored: only the brand and last 4
digits are kept.
"""

import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

import analytics
from auth import get_customer
from db import DB_PATH, cached_product, invalidate_products
from models import CartItemIn, CartLine, CartOut, CustomerContext, OrderLine, OrderOut
from validation import (
    card_brand, check_address, check_address2, check_card_number, check_city, check_cvv, check_email,
    check_expiry, check_full_name, check_phone, check_state, check_zip,
)

TAX_RATE = 0.0635  # Connecticut sales tax
SHIPPING_FEE = 5.95
FREE_SHIPPING_AT = 75.00
MAX_PER_LINE = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS carts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    visitor_id TEXT UNIQUE,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id INTEGER NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL REFERENCES catalogue(product_id),
    size TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (cart_id, product_id, size)
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT NOT NULL UNIQUE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    visitor_id TEXT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    address1 TEXT NOT NULL,
    address2 TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip TEXT NOT NULL,
    card_brand TEXT NOT NULL,
    card_last4 TEXT NOT NULL,
    item_count INTEGER NOT NULL,
    subtotal REAL NOT NULL,
    shipping REAL NOT NULL,
    tax REAL NOT NULL,
    total REAL NOT NULL,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    size TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    line_total REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cart_items_cart ON cart_items(cart_id);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
"""

router = APIRouter(prefix="/api", tags=["shop"])


@contextmanager
def connect_rw():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_shop_storage() -> None:
    with connect_rw() as con:
        con.executescript(SCHEMA)


def money(x: float) -> float:
    return round(x + 1e-9, 2)


# ---- Whose cart is it? ----------------------------------------------------------------

def _owner(request: Request, customer: CustomerContext | None) -> tuple[str, int | str]:
    if customer is not None:
        return "user_id", customer.user_id
    return "visitor_id", request.state.visitor_id


def _cart_id(con: sqlite3.Connection, column: str, value: int | str, create: bool) -> int | None:
    row = con.execute(f"SELECT id FROM carts WHERE {column} = ?", (value,)).fetchone()
    if row:
        return row["id"]
    if not create:
        return None
    return con.execute(f"INSERT INTO carts ({column}) VALUES (?)", (value,)).lastrowid


def _touch(con: sqlite3.Connection, cart_id: int) -> None:
    con.execute("UPDATE carts SET updated_at = datetime('now') WHERE id = ?", (cart_id,))


def _stock(product: dict, size: str) -> int | None:
    return next((i["quantity"] for i in product["inventory"] if i["size"] == size), None)


# ---- Reading a cart ---------------------------------------------------------------------

def build_cart(con: sqlite3.Connection, cart_id: int | None, signed_in: bool) -> CartOut:
    """Price the cart from the current catalogue. Lines beyond the stock on hand are trimmed."""
    lines: list[CartLine] = []
    if cart_id is not None:
        rows = con.execute(
            "SELECT id, product_id, size, quantity FROM cart_items WHERE cart_id = ? ORDER BY added_at, id", (cart_id,)
        ).fetchall()
        for r in rows:
            product = cached_product(r["product_id"])
            available = _stock(product, r["size"]) if product else None
            if product is None or available is None:
                con.execute("DELETE FROM cart_items WHERE id = ?", (r["id"],))
                continue
            qty, warning = r["quantity"], None
            if available == 0:
                warning = f"Size {r['size']} just sold out"
            elif qty > available:
                qty, warning = available, f"Only {available} left in {r['size']}; quantity reduced"
                con.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (qty, r["id"]))
            lines.append(CartLine(
                product_id=product["product_id"], name=product["name"], category=product["category"],
                size=r["size"], quantity=qty, unit_price=product["price"],
                line_total=money(product["price"] * qty if available else 0), thumb_url=product["thumb_url"],
                available=available, warning=warning,
            ))
    subtotal = money(sum(l.line_total for l in lines))
    count = sum(l.quantity for l in lines if l.available)
    shipping = 0.0 if subtotal == 0 or subtotal >= FREE_SHIPPING_AT else SHIPPING_FEE
    tax = money(subtotal * TAX_RATE)
    return CartOut(
        items=lines, item_count=count, subtotal=subtotal, shipping=shipping, tax=tax,
        total=money(subtotal + shipping + tax), free_shipping_at=FREE_SHIPPING_AT,
        free_shipping_remaining=money(max(0.0, FREE_SHIPPING_AT - subtotal)) if subtotal else FREE_SHIPPING_AT,
        tax_rate=TAX_RATE, saved_to_account=signed_in,
    )


def merge_visitor_cart(visitor_id: str | None, user_id: int) -> None:
    """On login/signup: move a guest's cart into the account's saved cart (capped at stock)."""
    if not visitor_id:
        return
    with connect_rw() as con:
        guest = _cart_id(con, "visitor_id", visitor_id, create=False)
        if guest is None:
            return
        items = con.execute("SELECT product_id, size, quantity FROM cart_items WHERE cart_id = ?", (guest,)).fetchall()
        if items:
            mine = _cart_id(con, "user_id", user_id, create=True)
            for it in items:
                product = cached_product(it["product_id"])
                cap = min(MAX_PER_LINE, _stock(product, it["size"]) or 0) if product else 0
                if cap <= 0:
                    continue
                con.execute(
                    "INSERT INTO cart_items (cart_id, product_id, size, quantity) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(cart_id, product_id, size) DO UPDATE SET quantity = MIN(?, quantity + excluded.quantity)",
                    (mine, it["product_id"], it["size"], min(cap, it["quantity"]), cap),
                )
            _touch(con, mine)
        con.execute("DELETE FROM carts WHERE id = ?", (guest,))


# ---- Cart routes ----------------------------------------------------------------------

def _product_or_404(product_id: str) -> dict:
    product = cached_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/cart", response_model=CartOut)
def get_cart(request: Request, customer: CustomerContext | None = Depends(get_customer)):
    column, owner = _owner(request, customer)
    with connect_rw() as con:
        return build_cart(con, _cart_id(con, column, owner, create=False), customer is not None)


@router.post("/cart/items", response_model=CartOut)
def add_to_cart(item: CartItemIn, request: Request, customer: CustomerContext | None = Depends(get_customer)):
    product = _product_or_404(item.product_id)
    available = _stock(product, item.size)
    if available is None:
        raise HTTPException(status_code=400, detail=f"{product['name']} doesn't come in size {item.size}.")
    if available == 0:
        raise HTTPException(status_code=409, detail=f"Sorry, {product['name']} is sold out in size {item.size}.")
    qty = max(1, item.quantity)
    column, owner = _owner(request, customer)
    with connect_rw() as con:
        cart = _cart_id(con, column, owner, create=True)
        row = con.execute(
            "SELECT quantity FROM cart_items WHERE cart_id = ? AND product_id = ? AND size = ?", (cart, item.product_id, item.size)
        ).fetchone()
        have = row["quantity"] if row else 0
        cap = min(available, MAX_PER_LINE)
        if have >= cap:
            raise HTTPException(
                status_code=409,
                detail=f"You already have {have} in your cart"
                + (f", and only {available} are in stock in size {item.size}." if available <= MAX_PER_LINE
                   else f" (limit {MAX_PER_LINE} per size)."),
            )
        added = min(qty, cap - have)
        con.execute(
            "INSERT INTO cart_items (cart_id, product_id, size, quantity) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(cart_id, product_id, size) DO UPDATE SET quantity = quantity + excluded.quantity",
            (cart, item.product_id, item.size, added),
        )
        _touch(con, cart)
        out = build_cart(con, cart, customer is not None)
    analytics.record(request, customer, "cart_add", product_id=item.product_id, size=item.size,
                     quantity=added, value=money(added * product["price"]))
    return out


@router.patch("/cart/items", response_model=CartOut)
def update_cart_item(item: CartItemIn, request: Request, customer: CustomerContext | None = Depends(get_customer)):
    """Set a line's quantity (0 removes it)."""
    product = _product_or_404(item.product_id)
    column, owner = _owner(request, customer)
    with connect_rw() as con:
        cart = _cart_id(con, column, owner, create=False)
        row = con.execute(
            "SELECT id, quantity FROM cart_items WHERE cart_id = ? AND product_id = ? AND size = ?",
            (cart, item.product_id, item.size),
        ).fetchone() if cart else None
        if row is None:
            raise HTTPException(status_code=404, detail="That item isn't in your cart.")
        available = _stock(product, item.size) or 0
        qty = min(item.quantity, available, MAX_PER_LINE)
        note = None
        if 0 < qty < item.quantity:
            note = f"Only {available} in stock in size {item.size}" if available < MAX_PER_LINE else f"Limit {MAX_PER_LINE} per size"
        if qty <= 0:
            con.execute("DELETE FROM cart_items WHERE id = ?", (row["id"],))
        else:
            con.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (qty, row["id"]))
        _touch(con, cart)
        out = build_cart(con, cart, customer is not None)
    delta = max(qty, 0) - row["quantity"]
    if delta:
        analytics.record(request, customer, "cart_add" if delta > 0 else "cart_remove", product_id=item.product_id,
                         size=item.size, quantity=abs(delta), value=money(abs(delta) * product["price"]))
    if note:
        for line in out.items:
            if line.product_id == item.product_id and line.size == item.size:
                line.warning = note
    return out


@router.delete("/cart/items", response_model=CartOut)
def remove_cart_item(product_id: str, size: str, request: Request, customer: CustomerContext | None = Depends(get_customer)):
    return update_cart_item(CartItemIn(product_id=product_id, size=size, quantity=0), request, customer)


@router.delete("/cart", response_model=CartOut)
def clear_cart(request: Request, customer: CustomerContext | None = Depends(get_customer)):
    column, owner = _owner(request, customer)
    with connect_rw() as con:
        cart = _cart_id(con, column, owner, create=False)
        if cart:
            con.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart,))
            _touch(con, cart)
        return build_cart(con, cart, customer is not None)


# ---- Checkout -----------------------------------------------------------------------------

CHECKOUT_RULES = {
    "full_name": check_full_name, "email": check_email, "phone": check_phone, "address1": check_address,
    "address2": check_address2, "city": check_city, "state": check_state, "zip": check_zip,
    "card_number": check_card_number, "expiry": check_expiry,
}


class CheckoutRequest(BaseModel):
    """Every field is checked with the rules in validation.py; errors come back per field."""

    full_name: str
    email: str
    phone: str
    address1: str
    address2: str = ""
    city: str
    state: str
    zip: str
    card_name: str
    card_number: str
    expiry: str
    cvv: str

    @field_validator("full_name", "email", "phone", "address1", "address2", "city", "state", "zip", "card_number", "expiry")
    @classmethod
    def check_field(cls, v: str, info) -> str:
        return CHECKOUT_RULES[info.field_name](v)

    @field_validator("card_name")
    @classmethod
    def check_card_name(cls, v: str) -> str:
        return check_full_name(v, "Name on card")

    @field_validator("cvv")
    @classmethod
    def check_security_code(cls, v: str, info) -> str:
        # Amex codes are 4 digits, other cards 3 (card_number is checked first, so it's available here).
        return check_cvv(v, info.data.get("card_number"))


def _order_number(con: sqlite3.Connection) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        number = f"CC-{datetime.now(timezone.utc):%y%m%d}-" + "".join(secrets.choice(alphabet) for _ in range(5))
        if not con.execute("SELECT 1 FROM orders WHERE order_number = ?", (number,)).fetchone():
            return number


@router.post("/checkout", response_model=OrderOut, status_code=201)
def checkout(req: CheckoutRequest, request: Request, customer: CustomerContext | None = Depends(get_customer)):
    column, owner = _owner(request, customer)
    with connect_rw() as con:
        con.execute("BEGIN IMMEDIATE")  # lock so two checkouts can't sell the same last item
        cart_id = _cart_id(con, column, owner, create=False)
        cart = build_cart(con, cart_id, customer is not None)
        lines = [l for l in cart.items if l.available > 0]
        if not lines:
            raise HTTPException(status_code=400, detail="Your cart is empty.")
        for l in lines:  # check live stock again inside the transaction
            live = con.execute(
                "SELECT quantity FROM inventory WHERE product_id = ? AND size = ?", (l.product_id, l.size)
            ).fetchone()
            if live is None or live["quantity"] < l.quantity:
                raise HTTPException(status_code=409, detail=f"{l.name} (size {l.size}) no longer has {l.quantity} in stock. Please review your cart.")
        number = _order_number(con)
        brand = card_brand(req.card_number)[0]
        order_id = con.execute(
            "INSERT INTO orders (order_number, user_id, visitor_id, full_name, email, phone, address1, address2, city, state, zip, "
            "card_brand, card_last4, item_count, subtotal, shipping, tax, total) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (number, customer.user_id if customer else None, request.state.visitor_id, req.full_name, req.email, req.phone,
             req.address1, req.address2, req.city, req.state, req.zip, brand, req.card_number[-4:],
             cart.item_count, cart.subtotal, cart.shipping, cart.tax, cart.total),
        ).lastrowid
        con.executemany(
            "INSERT INTO order_items (order_id, product_id, product_name, category, size, quantity, unit_price, line_total) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [(order_id, l.product_id, l.name, l.category, l.size, l.quantity, l.unit_price, l.line_total) for l in lines],
        )
        con.executemany(
            "UPDATE inventory SET quantity = quantity - ? WHERE product_id = ? AND size = ?",
            [(l.quantity, l.product_id, l.size) for l in lines],
        )
        con.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
        _touch(con, cart_id)
    invalidate_products()  # stock changed
    analytics.record(request, customer, "order_placed", quantity=cart.item_count, value=cart.total, detail={"order_number": number})
    return get_order(number, request, customer)


@router.get("/orders/{order_number}", response_model=OrderOut)
def get_order(order_number: str, request: Request, customer: CustomerContext | None = Depends(get_customer)):
    """An order's receipt. Only the shopper who placed it (their account or their browser) can see it."""
    with connect_rw() as con:
        o = con.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,)).fetchone()
        mine = o is not None and (
            (customer is not None and o["user_id"] == customer.user_id) or o["visitor_id"] == request.state.visitor_id
        )
        if not mine:
            raise HTTPException(status_code=404, detail="Order not found")
        items = con.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (o["id"],)).fetchall()
    address = ", ".join(x for x in [o["address1"], o["address2"], o["city"], f"{o['state']} {o['zip']}"] if x)
    return OrderOut(
        order_number=o["order_number"], created_at=o["created_at"], full_name=o["full_name"], email=o["email"],
        phone=o["phone"], ship_to=address, card=f"{o['card_brand']} ending in {o['card_last4']}",
        items=[OrderLine(product_id=i["product_id"], name=i["product_name"], size=i["size"], quantity=i["quantity"],
                         unit_price=i["unit_price"], line_total=i["line_total"],
                         thumb_url=(cached_product(i["product_id"]) or {}).get("thumb_url")) for i in items],
        item_count=o["item_count"], subtotal=o["subtotal"], shipping=o["shipping"], tax=o["tax"], total=o["total"],
    )
