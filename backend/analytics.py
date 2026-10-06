"""Shop analytics and the admin dashboard.

Tracking: every meaningful shopper action is written to the analytics_events table:
  search          the header search bar and the chat assistant (query, how many results)
  product_view    a product page was opened (at most once per shopper per product per 30 minutes)
  cart_add        items added to a cart (product, size, quantity, value)
  cart_remove     items taken out of a cart
  checkout_started the checkout page was opened with items in the cart
  compare         products were compared side by side
  order_placed    a checkout went through (order number, units, total)
Shoppers are identified only by their account id (signed in) or an anonymous browser id.

Abandoned carts are read straight from the carts table: a cart with items that hasn't changed in
ABANDONED_AFTER_MINUTES. Checkout empties the cart, so a completed purchase is never counted.

Dashboard: GET /api/admin/analytics, for admins only (users.is_admin = 1). Accounts listed in
the ADMIN_EMAILS environment variable (default: the test account) are made admins at startup.

Sample data: an admin can load clearly-flagged sample activity (is_demo = 1) to see the dashboard
filled in, and remove it again with one click. Sample orders never change real stock.
"""

import json
import os
import random
import sqlite3
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from auth import current_user_row, get_customer
from db import DB_PATH, cached_product, cached_products
from models import CustomerContext

ABANDONED_AFTER_MINUTES = 30
VIEW_DEDUPE_MINUTES = 30
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "test@campuscustoms.yale.edu").split(",") if e.strip()]
CLIENT_EVENTS = {"product_view", "checkout_started", "compare"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    visitor_id TEXT,
    product_id TEXT,
    size TEXT,
    query TEXT,
    source TEXT,
    results INTEGER,
    quantity INTEGER,
    value REAL,
    detail TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON analytics_events(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_events_time ON analytics_events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_product ON analytics_events(product_id, event_type);
"""


@contextmanager
def connect_rw():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_analytics_storage() -> None:
    """Create the events table, add users.is_admin, and promote ADMIN_EMAILS. Safe on every start."""
    with connect_rw() as con:
        con.executescript(SCHEMA)
        columns = {r["name"] for r in con.execute("PRAGMA table_info(users)")}
        if "is_admin" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        con.executemany("UPDATE users SET is_admin = 1 WHERE lower(email) = ?", [(e,) for e in ADMIN_EMAILS])


# ---- Recording events -------------------------------------------------------------------

def record(request: Request, customer: CustomerContext | None, event_type: str, **fields) -> None:
    """Write one event. Tracking must never break the shop, so errors are swallowed."""
    detail = fields.pop("detail", None)
    try:
        with connect_rw() as con:
            con.execute(
                "INSERT INTO analytics_events (event_type, user_id, visitor_id, product_id, size, query, source, results, "
                "quantity, value, detail) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (event_type, customer.user_id if customer else None, getattr(request.state, "visitor_id", None),
                 fields.get("product_id"), fields.get("size"), fields.get("query"), fields.get("source"),
                 fields.get("results"), fields.get("quantity"), fields.get("value"),
                 json.dumps(detail) if detail else None),
            )
    except sqlite3.Error:
        pass


def record_search(request: Request, customer: CustomerContext | None, query: str, results: int, source: str) -> None:
    record(request, customer, "search", query=query.strip()[:100], results=results, source=source)


class ClientEvent(BaseModel):
    type: str = Field(max_length=30)
    product_id: str | None = Field(default=None, max_length=120)
    product_ids: list[str] = Field(default_factory=list, max_length=6)


router = APIRouter(prefix="/api", tags=["analytics"])


@router.post("/events", status_code=204)
def client_event(event: ClientEvent, request: Request, customer: CustomerContext | None = Depends(get_customer)):
    """Events only the browser knows about: product pages opened, checkout opened, comparisons."""
    if event.type not in CLIENT_EVENTS:
        raise HTTPException(status_code=400, detail="Unknown event type.")
    if event.type == "product_view":
        if not event.product_id or cached_product(event.product_id) is None:
            raise HTTPException(status_code=404, detail="Product not found")
        with connect_rw() as con:
            seen = con.execute(
                "SELECT 1 FROM analytics_events WHERE event_type = 'product_view' AND product_id = ? AND visitor_id = ? "
                "AND created_at > datetime('now', ?)",
                (event.product_id, request.state.visitor_id, f"-{VIEW_DEDUPE_MINUTES} minutes"),
            ).fetchone()
        if not seen:
            record(request, customer, "product_view", product_id=event.product_id)
    elif event.type == "compare":
        ids = [i for i in event.product_ids if cached_product(i)]
        if len(ids) >= 2:
            record(request, customer, "compare", quantity=len(ids), detail={"product_ids": ids})
    else:
        record(request, customer, event.type)


# ---- Admin access --------------------------------------------------------------------------

def is_admin(request: Request) -> bool:
    row = current_user_row(request)
    return bool(row is not None and "is_admin" in row.keys() and row["is_admin"])


def require_admin(request: Request) -> CustomerContext:
    customer = get_customer(request)
    if customer is None:
        raise HTTPException(status_code=401, detail="Please log in with an admin account.")
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="This page is for Campus Customs admins only.")
    return customer


admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---- The dashboard -------------------------------------------------------------------------

def _since(days: int) -> str:
    if days <= 0:
        return "0000-00-00"
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def _pct(part: float, whole: float) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def _product_brief(pid: str) -> dict:
    p = cached_product(pid)
    if p is None:
        return {"product_id": pid, "name": pid, "category": "", "thumb_url": None, "price": None, "total_stock": None}
    return {"product_id": pid, "name": p["name"], "category": p["category"], "thumb_url": p["thumb_url"],
            "price": p["price"], "total_stock": p["total_stock"]}


@admin_router.get("/analytics")
def dashboard(days: int = Query(30, ge=0, le=3650), admin: CustomerContext = Depends(require_admin)) -> dict:
    """Everything on the admin dashboard in one response. days=0 means all time."""
    since = _since(days)
    with connect_rw() as con:
        events = con.execute(
            "SELECT event_type, user_id, visitor_id, product_id, size, query, source, results, quantity, value, is_demo, "
            "created_at FROM analytics_events WHERE created_at >= ? ORDER BY created_at", (since,)
        ).fetchall()
        orders = con.execute(
            "SELECT o.*, u.name AS account_name FROM orders o LEFT JOIN users u ON u.id = o.user_id "
            "WHERE o.created_at >= ? ORDER BY o.created_at DESC", (since,)
        ).fetchall()
        order_items = con.execute(
            "SELECT i.*, o.created_at FROM order_items i JOIN orders o ON o.id = i.order_id WHERE o.created_at >= ?", (since,)
        ).fetchall()
        carts = con.execute(
            "SELECT c.id, c.user_id, c.visitor_id, c.is_demo, c.updated_at, u.name, u.email FROM carts c "
            "LEFT JOIN users u ON u.id = c.user_id "
            "WHERE c.updated_at >= ? AND c.updated_at < datetime('now', ?) "
            "AND EXISTS (SELECT 1 FROM cart_items i WHERE i.cart_id = c.id)",
            (since, f"-{ABANDONED_AFTER_MINUTES} minutes"),
        ).fetchall()
        cart_items = defaultdict(list)
        if carts:
            marks = ",".join("?" * len(carts))
            for r in con.execute(f"SELECT cart_id, product_id, size, quantity FROM cart_items WHERE cart_id IN ({marks})",
                                 [c["id"] for c in carts]):
                cart_items[r["cart_id"]].append(r)
        low_stock = con.execute(
            "SELECT product_id, size, quantity FROM inventory WHERE quantity <= 5 ORDER BY quantity, product_id"
        ).fetchall()
        demo_rows = con.execute(
            "SELECT (SELECT COUNT(*) FROM analytics_events WHERE is_demo = 1) + (SELECT COUNT(*) FROM orders WHERE is_demo = 1) "
            "+ (SELECT COUNT(*) FROM carts WHERE is_demo = 1)"
        ).fetchone()[0]

    who = lambda e: e["visitor_id"] or f"user-{e['user_id']}"
    by_type = defaultdict(list)
    for e in events:
        by_type[e["event_type"]].append(e)

    # ---- Orders and revenue
    revenue = round(sum(o["total"] for o in orders), 2)
    merchandise = round(sum(o["subtotal"] for o in orders), 2)
    units_sold = sum(i["quantity"] for i in order_items)
    order_count = len(orders)

    # ---- Abandoned carts (priced at today's prices)
    abandoned = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for c in carts:
        items = []
        for it in cart_items[c["id"]]:
            p = _product_brief(it["product_id"])
            items.append({**p, "size": it["size"], "quantity": it["quantity"],
                          "line_total": round((p["price"] or 0) * it["quantity"], 2)})
        idle = now - datetime.fromisoformat(c["updated_at"])
        abandoned.append({
            "cart_id": c["id"], "shopper": c["name"] or "Guest shopper", "email": c["email"],
            "signed_in": c["user_id"] is not None, "is_demo": bool(c["is_demo"]), "last_active": c["updated_at"],
            "idle_hours": round(idle.total_seconds() / 3600, 1), "items": items,
            "units": sum(i["quantity"] for i in items), "value": round(sum(i["line_total"] for i in items), 2),
        })
    abandoned.sort(key=lambda a: -a["value"])
    abandoned_value = round(sum(a["value"] for a in abandoned), 2)

    # ---- Traffic and the funnel (unique shoppers at each step)
    visitors = {who(e) for e in events} | {o["visitor_id"] or f"user-{o['user_id']}" for o in orders}
    step = lambda t: {who(e) for e in by_type[t]}
    buyers = {o["visitor_id"] or f"user-{o['user_id']}" for o in orders}
    funnel = [
        {"step": "Visited the shop", "shoppers": len(visitors)},
        {"step": "Viewed a product", "shoppers": len(step("product_view") | step("cart_add") | buyers)},
        {"step": "Added to cart", "shoppers": len(step("cart_add") | buyers)},
        {"step": "Started checkout", "shoppers": len(step("checkout_started") | buyers)},
        {"step": "Placed an order", "shoppers": len(buyers)},
    ]
    top = funnel[0]["shoppers"]
    for i, f in enumerate(funnel):
        f["pct_of_visitors"] = _pct(f["shoppers"], top)
        f["pct_of_previous"] = _pct(f["shoppers"], funnel[i - 1]["shoppers"]) if i else 100.0

    # ---- Searches
    searches = by_type["search"]
    grouped = defaultdict(list)
    for s in searches:
        grouped[(s["query"] or "").strip().lower()].append(s)
    search_rows = []
    for q, rows in grouped.items():
        if not q:
            continue
        sources = Counter(r["source"] or "search_bar" for r in rows)
        search_rows.append({
            "query": q, "count": len(rows), "avg_results": round(sum(r["results"] or 0 for r in rows) / len(rows), 1),
            "zero_results": sum(1 for r in rows if not r["results"]), "last_searched": rows[-1]["created_at"],
            "search_bar": sources.get("search_bar", 0), "chat": sources.get("chat", 0),
        })
    search_rows.sort(key=lambda r: (-r["count"], r["query"]))
    zero = [r for r in search_rows if r["zero_results"] == r["count"]]

    # ---- Products
    stats = defaultdict(lambda: {"views": 0, "cart_adds": 0, "cart_add_units": 0, "units_sold": 0, "revenue": 0.0,
                                 "orders": set(), "compared": 0})
    for e in by_type["product_view"]:
        stats[e["product_id"]]["views"] += 1
    for e in by_type["cart_add"]:
        stats[e["product_id"]]["cart_adds"] += 1
        stats[e["product_id"]]["cart_add_units"] += e["quantity"] or 0
    for i in order_items:
        s = stats[i["product_id"]]
        s["units_sold"] += i["quantity"]
        s["revenue"] += i["line_total"]
        s["orders"].add(i["order_id"])
    popular = []
    for pid, s in stats.items():
        if not pid:
            continue
        score = s["views"] + 3 * s["cart_add_units"] + 5 * s["units_sold"]
        popular.append({**_product_brief(pid), "views": s["views"], "cart_adds": s["cart_adds"],
                        "cart_add_units": s["cart_add_units"], "units_sold": s["units_sold"],
                        "revenue": round(s["revenue"], 2), "orders": len(s["orders"]),
                        "view_to_cart_pct": _pct(s["cart_adds"], s["views"]), "score": score})
    popular.sort(key=lambda p: (-p["score"], p["name"]))

    # ---- What was checked out
    checked = defaultdict(lambda: {"units": 0, "revenue": 0.0, "orders": set()})
    by_category = defaultdict(lambda: {"units": 0, "revenue": 0.0})
    sizes = Counter()
    for i in order_items:
        c = checked[(i["product_id"], i["size"])]
        c["units"] += i["quantity"]
        c["revenue"] += i["line_total"]
        c["orders"].add(i["order_id"])
        by_category[i["category"]]["units"] += i["quantity"]
        by_category[i["category"]]["revenue"] += i["line_total"]
        sizes[i["size"]] += i["quantity"]
    checked_out = sorted(
        ({**_product_brief(pid), "size": size, "units": c["units"], "revenue": round(c["revenue"], 2), "orders": len(c["orders"])}
         for (pid, size), c in checked.items()),
        key=lambda r: (-r["units"], -r["revenue"]),
    )
    categories = sorted(
        ({"category": k, "units": v["units"], "revenue": round(v["revenue"], 2), "share_pct": _pct(v["revenue"], merchandise)}
         for k, v in by_category.items()),
        key=lambda r: -r["revenue"],
    )

    # ---- Day by day
    if days > 0:
        first_day = datetime.fromisoformat(since[:10]).date()
    else:  # all time: start at the earliest event or order
        starts = [e["created_at"] for e in events[:1]] + [o["created_at"] for o in orders[-1:]]
        first_day = min(datetime.fromisoformat(t).date() for t in starts) if starts else now.date()
    daily = {}
    d = first_day
    while d <= now.date():
        daily[d.isoformat()] = {"date": d.isoformat(), "revenue": 0.0, "orders": 0, "views": 0, "searches": 0, "cart_adds": 0,
                                "visitors": set()}
        d += timedelta(days=1)
    for e in events:
        day = daily.get(e["created_at"][:10])
        if day is None:
            continue
        day["visitors"].add(who(e))
        key = {"product_view": "views", "search": "searches", "cart_add": "cart_adds"}.get(e["event_type"])
        if key:
            day[key] += 1
    for o in orders:
        day = daily.get(o["created_at"][:10])
        if day:
            day["revenue"] = round(day["revenue"] + o["total"], 2)
            day["orders"] += 1
    daily_rows = [{**v, "visitors": len(v["visitors"])} for v in daily.values()]

    # ---- Recent orders
    items_by_order = defaultdict(list)
    for i in order_items:
        items_by_order[i["order_id"]].append(f"{i['quantity']}× {i['product_name']} ({i['size']})")
    recent = [{
        "order_number": o["order_number"], "created_at": o["created_at"], "customer": o["full_name"], "email": o["email"],
        "signed_in": o["user_id"] is not None, "items": items_by_order[o["id"]], "units": o["item_count"],
        "total": o["total"], "city": f"{o['city']}, {o['state']}", "is_demo": bool(o["is_demo"]),
    } for o in orders[:20]]

    cart_add_events = len(by_type["cart_add"])
    attempts = len(abandoned) + order_count
    return {
        "range_days": days,
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "abandoned_after_minutes": ABANDONED_AFTER_MINUTES,
        "includes_sample_data": demo_rows > 0,
        "kpis": {
            "revenue": revenue, "merchandise_sales": merchandise, "orders": order_count, "units_sold": units_sold,
            "avg_order_value": round(revenue / order_count, 2) if order_count else 0.0,
            "units_per_order": round(units_sold / order_count, 2) if order_count else 0.0,
            "visitors": len(visitors), "product_views": len(by_type["product_view"]), "searches": len(searches),
            "zero_result_searches": sum(1 for s in searches if not s["results"]),
            "zero_result_rate": _pct(sum(1 for s in searches if not s["results"]), len(searches)),
            "cart_adds": cart_add_events, "cart_add_units": sum(e["quantity"] or 0 for e in by_type["cart_add"]),
            "cart_removes": len(by_type["cart_remove"]), "checkouts_started": len(step("checkout_started")),
            "comparisons": len(by_type["compare"]), "conversion_rate": _pct(len(buyers), len(visitors)),
            "abandoned_carts": len(abandoned), "abandoned_value": abandoned_value,
            "cart_abandonment_rate": _pct(len(abandoned), attempts),
        },
        "daily": daily_rows,
        "funnel": funnel,
        "top_searches": search_rows[:15],
        "zero_result_searches": zero[:10],
        "search_sources": {"search_bar": sum(r["search_bar"] for r in search_rows), "chat": sum(r["chat"] for r in search_rows)},
        "popular_products": popular[:15],
        "checked_out_items": checked_out[:20],
        "sales_by_category": categories,
        "sizes_sold": [{"size": s, "units": sizes[s]} for s in ["XS", "S", "M", "L", "XL", "XXL"] if sizes[s]],
        "abandoned_carts": abandoned[:25],
        "recent_orders": recent,
        "low_stock": [{**_product_brief(r["product_id"]), "size": r["size"], "quantity": r["quantity"]} for r in low_stock][:40],
        "low_stock_counts": {"out_of_stock": sum(1 for r in low_stock if r["quantity"] == 0),
                             "low": sum(1 for r in low_stock if r["quantity"] > 0)},
    }


# ---- Sample data (clearly flagged, removable) ---------------------------------------------

SAMPLE_SEARCHES = ["hoodies", "t-shirts", "quarter-zips", "gray hoodie", "hockey", "jackets", "crewneck", "under $40",
                   "football", "navy", "fleece", "baseball t shirt", "long sleeve", "tri blend", "college crest"]
SAMPLE_MISSES = ["socks", "baseball cap", "dog bandana", "sweatpants", "water bottle"]
SAMPLE_PEOPLE = [("Jordan Lee", "New Haven", "CT", "06511"), ("Priya Shah", "Hamden", "CT", "06517"),
                 ("Sam Carter", "Boston", "MA", "02116"), ("Maya Chen", "New York", "NY", "10027"),
                 ("Chris Alvarez", "Stamford", "CT", "06901"), ("Taylor Brooks", "Providence", "RI", "02903")]


@admin_router.post("/sample-data")
def load_sample_data(admin: CustomerContext = Depends(require_admin)) -> dict:
    """Fill the dashboard with 45 days of sample activity, flagged is_demo = 1. Real stock is not changed."""
    from tools import catalogue_search

    rng = random.Random(409)
    products = cached_products()
    weights = [rng.randint(1, 7) for _ in products]  # some products are more popular than others
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stamp = lambda t: t.strftime("%Y-%m-%d %H:%M:%S")
    result_counts = {q: catalogue_search(q).total_matches for q in SAMPLE_SEARCHES + SAMPLE_MISSES}
    events, orders = [], []
    for n in range(420):
        visitor = f"sample-{n:04d}"
        t = now - timedelta(days=rng.uniform(0.1, 45), hours=rng.uniform(0, 3))
        if rng.random() < 0.55:
            q = rng.choice(SAMPLE_MISSES) if rng.random() < 0.12 else rng.choice(SAMPLE_SEARCHES)
            events.append(("search", visitor, None, None, q, rng.choice(["search_bar", "search_bar", "chat"]), result_counts[q], None, None, stamp(t)))
            t += timedelta(minutes=rng.uniform(0.3, 3))
        viewed = rng.choices(products, weights, k=rng.randint(1, 4))
        for p in viewed:
            events.append(("product_view", visitor, p["product_id"], None, None, None, None, None, None, stamp(t)))
            t += timedelta(minutes=rng.uniform(0.5, 4))
        if rng.random() < 0.08 and len(viewed) >= 2:
            events.append(("compare", visitor, None, None, None, None, None, len(viewed), None, stamp(t)))
        if rng.random() < 0.34:
            basket = []
            for p in viewed[: rng.randint(1, len(viewed))]:
                sizes = [i["size"] for i in p["inventory"] if i["quantity"] > 0]
                if sizes:
                    size, qty = rng.choice(sizes), rng.choice([1, 1, 1, 2])
                    basket.append((p, size, qty))
                    events.append(("cart_add", visitor, p["product_id"], size, None, None, None, qty, round(p["price"] * qty, 2), stamp(t)))
                    t += timedelta(minutes=rng.uniform(0.3, 2))
            if basket and rng.random() < 0.62:
                events.append(("checkout_started", visitor, None, None, None, None, None, None, None, stamp(t)))
                t += timedelta(minutes=rng.uniform(1, 6))
                if rng.random() < 0.72:
                    orders.append((visitor, basket, t))
                    events.append(("order_placed", visitor, None, None, None, None, None, sum(q for _, _, q in basket), None, stamp(t)))
            elif basket:
                orders.append((visitor, basket, None))  # left in the cart
    with connect_rw() as con:
        con.executemany(
            "INSERT INTO analytics_events (event_type, visitor_id, product_id, size, query, source, results, quantity, value, "
            "created_at, is_demo) VALUES (?,?,?,?,?,?,?,?,?,?,1)", events,
        )
        placed = abandoned = 0
        for visitor, basket, t in orders:
            if t is None:
                if abandoned >= 14:
                    continue
                abandoned += 1
                cart = con.execute("INSERT INTO carts (visitor_id, is_demo, created_at, updated_at) VALUES (?, 1, ?, ?)",
                                   (visitor, stamp(now - timedelta(days=rng.uniform(0.1, 9))), stamp(now - timedelta(hours=rng.uniform(1, 200))))).lastrowid
                con.executemany("INSERT OR IGNORE INTO cart_items (cart_id, product_id, size, quantity) VALUES (?,?,?,?)",
                                [(cart, p["product_id"], size, q) for p, size, q in basket])
                continue
            name, city, state, zip_code = rng.choice(SAMPLE_PEOPLE)
            subtotal = round(sum(p["price"] * q for p, _, q in basket), 2)
            shipping = 0.0 if subtotal >= 75 else 5.95
            tax = round(subtotal * 0.0635, 2)
            placed += 1
            order_id = con.execute(
                "INSERT INTO orders (order_number, visitor_id, full_name, email, phone, address1, city, state, zip, card_brand, "
                "card_last4, item_count, subtotal, shipping, tax, total, is_demo, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
                (f"SAMPLE-{placed:04d}", visitor, name, name.split()[0].lower() + "@example.com", "(203) 555-0100",
                 "100 Sample St", city, state, zip_code, "Visa", "4242", sum(q for _, _, q in basket), subtotal, shipping, tax,
                 round(subtotal + shipping + tax, 2), stamp(t)),
            ).lastrowid
            con.executemany(
                "INSERT INTO order_items (order_id, product_id, product_name, category, size, quantity, unit_price, line_total) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [(order_id, p["product_id"], p["name"], p["category"], size, q, p["price"], round(p["price"] * q, 2)) for p, size, q in basket],
            )
    return {"events": len(events), "orders": placed, "abandoned_carts": abandoned}


@admin_router.delete("/sample-data")
def clear_sample_data(admin: CustomerContext = Depends(require_admin)) -> dict:
    with connect_rw() as con:
        e = con.execute("DELETE FROM analytics_events WHERE is_demo = 1").rowcount
        o = con.execute("DELETE FROM orders WHERE is_demo = 1").rowcount
        c = con.execute("DELETE FROM carts WHERE is_demo = 1").rowcount
    return {"events": e, "orders": o, "abandoned_carts": c}
