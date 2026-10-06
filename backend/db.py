"""Shared read-only access to campus_customs.db and product shaping.

Both the product API endpoints (main.py) and the chatbot's tools (tools.py) load
products through here, so there is one definition of what a "product" looks like.

Speed: the whole catalogue (102 products + 612 inventory rows) is read with two queries and
kept in memory (`cached_products`). Checkout calls `invalidate_products()` after it changes
stock, and the cache also refreshes itself every few minutes in case the database is edited
by hand, so shoppers never see stale prices or stock for long.
"""

import json
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "campus_customs.db"
PRODUCTS_DIR = ROOT / "products"
OPTIMIZED_DIR = PRODUCTS_DIR / "optimized"  # compressed WebP copies (see images.py)
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
CACHE_SECONDS = 300


@contextmanager
def connect():
    # Read-only connection so nothing here can ever modify the shop's data.
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def category_for(garment_type: str) -> str:
    """Group the many free-text garment types into a few shopper-friendly categories."""
    g = garment_type.lower()
    if "t-shirt" in g:
        return "T-Shirts"
    if "hood" in g:
        return "Hoodies"
    if "quarter-zip" in g:
        return "Quarter-Zips"
    if "jacket" in g:
        return "Jackets"
    if "performance" in g:
        return "Long Sleeves"
    return "Crewnecks & Sweatshirts"


def short_description(text: str, limit: int = 110) -> str:
    first = text.split(". ")[0].rstrip(".") + "."
    return first if len(first) <= limit else first[: limit - 1].rsplit(" ", 1)[0] + "…"


# Fabric words the catalogue actually uses (in names, descriptions, or garment types).
# Products that don't name a fabric get None, shown as "Not listed", so nothing is invented.
MATERIALS = [
    ("tri blend", "Tri-blend"), ("tri-blend", "Tri-blend"), ("double knit", "Double knit"),
    ("fleece", "Fleece"), ("cotton", "Cotton"), ("heavyweight", "Heavyweight"), ("performance", "Performance fabric"),
    ("dry zone", "Performance fabric"), ("tech", "Performance fabric"),
]
FEATURES = [
    ("kangaroo pocket", "Kangaroo pocket"), ("drawstring", "Drawstring hood"), ("full-zip", "Full zip"),
    ("full-length", "Full zip"), ("quarter-zip", "Quarter zip"), ("1/4 zip", "Quarter zip"), ("stand collar", "Stand collar"),
    ("zippered", "Zip pockets"), ("hand pocket", "Hand pockets"), ("ribbed", "Ribbed cuffs & hem"),
    ("mock", "Mock neck"), ("raglan", "Raglan sleeves"), ("left chest", "Left-chest logo"), ("crest", "College crest"),
]


def material_for(name: str, garment_type: str, description: str) -> str | None:
    text = f"{name} {garment_type} {description}".lower()
    found = [label for word, label in MATERIALS if re.search(rf"\b{re.escape(word)}\b", text)]
    return " · ".join(dict.fromkeys(found)) or None


def features_for(garment_type: str, description: str, tags: list[str]) -> list[str]:
    text = f"{garment_type} {description} {' '.join(tags)}".lower()
    return list(dict.fromkeys(label for word, label in FEATURES if word in text))


def sleeve_for(garment_type: str, description: str) -> str:
    text = f"{garment_type} {description}".lower()
    if "short-sleeve" in text or "short sleeve" in text or "t-shirt" in text:
        return "Short sleeve"
    return "Long sleeve"


def image_urls(image_file_path: str) -> dict:
    """Original JPEG plus compressed WebP versions when images.py has made them."""
    original = "/media/" + image_file_path
    stem = Path(image_file_path).stem
    has = lambda name: (OPTIMIZED_DIR / f"{stem}-{name}.webp").exists()
    base = f"/media/products/optimized/{stem}"
    urls = {"image_url": original, "thumb_url": original, "original_image_url": original,
            "cutout_url": None, "cutout_thumb_url": None}
    if has("480") and has("320"):
        urls.update(image_url=f"{base}-480.webp", thumb_url=f"{base}-320.webp")
    if has("cut-640") and has("cut-320"):  # background removed, for the storefront's product stages
        urls.update(cutout_url=f"{base}-cut-640.webp", cutout_thumb_url=f"{base}-cut-320.webp")
    return urls


def to_product(row: sqlite3.Row, inventory: list[dict]) -> dict:
    inventory = sorted(inventory, key=lambda i: SIZE_ORDER.index(i["size"]) if i["size"] in SIZE_ORDER else 99)
    tags = json.loads(row["search_tags"])
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "category": category_for(row["garment_type"]),
        "description": row["description"],
        "short_description": short_description(row["description"]),
        "colors": json.loads(row["colors"]),
        "search_tags": tags,
        **image_urls(row["image_file_path"]),
        "price": row["price"],
        "inventory": inventory,
        "total_stock": sum(i["quantity"] for i in inventory),
        "material": material_for(row["name"], row["garment_type"], row["description"]),
        "features": features_for(row["garment_type"], row["description"], tags),
        "sleeve": sleeve_for(row["garment_type"], row["description"]),
    }


def load_products(con: sqlite3.Connection, product_id: str | None = None) -> list[dict]:
    where, params = ("WHERE product_id = ?", (product_id,)) if product_id else ("", ())
    rows = con.execute(f"SELECT * FROM catalogue {where} ORDER BY name", params).fetchall()
    inv: dict[str, list[dict]] = {}
    for r in con.execute(f"SELECT product_id, size, quantity FROM inventory {where}", params):
        inv.setdefault(r["product_id"], []).append({"size": r["size"], "quantity": r["quantity"]})
    return [to_product(r, inv.get(r["product_id"], [])) for r in rows]


# ---- In-memory catalogue cache -------------------------------------------------------

_cache: dict = {"products": None, "by_id": {}, "loaded_at": 0.0, "version": 0}
_cache_lock = threading.Lock()


def cached_products() -> list[dict]:
    """Every product, from memory. Reloads from the database after invalidate_products() or CACHE_SECONDS."""
    with _cache_lock:
        if _cache["products"] is None or time.monotonic() - _cache["loaded_at"] > CACHE_SECONDS:
            with connect() as con:
                products = load_products(con)
            _cache.update(products=products, by_id={p["product_id"]: p for p in products},
                          loaded_at=time.monotonic(), version=_cache["version"] + 1)
        return _cache["products"]


def cached_product(product_id: str) -> dict | None:
    cached_products()
    return _cache["by_id"].get(product_id)


def catalogue_version() -> int:
    """Changes whenever the cached catalogue is reloaded (used for the products ETag)."""
    cached_products()
    return _cache["version"]


def invalidate_products() -> None:
    with _cache_lock:
        _cache["products"] = None
