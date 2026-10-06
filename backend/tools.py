"""Tools the Campus Customs agent can call, plus a no-LLM keyword fallback.

Every tool reads the read-only catalogue (campus_customs.db) and returns a typed result
from models.py, so prices, descriptions, and stock counts reach the model exactly as they
are stored. Tools also record every product they return into `ctx.deps`; the chat endpoint
builds the website's product cards from those database rows, and rejects any product_id
the agent names that a tool didn't return.
"""

import re
from dataclasses import dataclass, field

from pydantic_ai import RunContext

import chat_store
from db import SIZE_ORDER, cached_products
from models import (
    ChatResponse,
    CustomerContext,
    CustomerProfile,
    PageContext,
    PageContextResult,
    PageProduct,
    PriceResult,
    ProductCard,
    ProductDescriptionResult,
    ProductMatch,
    ProductNotFound,
    ProductSearchResult,
    SearchResponse,
    SizeAvailability,
    StockResult,
    StockStatus,
)

MAX_RESULTS = 30  # Enough to show every item in the largest category (29).
LOW_STOCK_THRESHOLD = 5  # Same cut-off the product pages use for "Only N left".


@dataclass
class ChatDeps:
    """Per-request state passed to every tool call (PydanticAI "dependencies")."""

    # Who is chatting: the signed-in shopper from their session, or None for a guest.
    customer: CustomerContext | None = None
    # What page they're on, as sent by the website (ids only; details are looked up here).
    page: PageContext | None = None
    # product_id -> full product row, for every product a tool returned during this run.
    seen: dict[str, dict] = field(default_factory=dict)
    # (query, total matches) for each catalogue search this run, for the analytics dashboard.
    searches: list[tuple[str, int]] = field(default_factory=list)
    # Lookups the keyword fallback made (tool name, arguments, result), for the audit trail.
    trace: list[dict] = field(default_factory=list)

    def note(self, tool: str, args: dict, result) -> None:
        self.trace.append({"tool": tool, "args": args, "result": result})

    def record(self, products: list[dict]) -> None:
        for p in products:
            self.seen.setdefault(p["product_id"], p)

    def cards(self, product_ids: list[str]) -> list[ProductCard]:
        """Build product cards, in the given order, from the database rows the tools returned."""
        ids = list(dict.fromkeys(product_ids))  # drop duplicates, keep order
        return [ProductCard(**self.seen[i]) for i in ids if i in self.seen][:MAX_RESULTS]


# ---- Helpers ---------------------------------------------------------------------

def _all_products() -> list[dict]:
    return cached_products()  # in-memory catalogue (db.py), refreshed when stock changes


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _match(p: dict) -> ProductMatch:
    return ProductMatch(
        product_id=p["product_id"], name=p["name"], category=p["category"],
        price=p["price"], total_stock=p["total_stock"],
    )


def _status(quantity: int) -> StockStatus:
    if quantity == 0:
        return "out_of_stock"
    return "low_stock" if quantity <= LOW_STOCK_THRESHOLD else "in_stock"


SIZE_ALIASES = {
    "xs": "XS", "x-small": "XS", "xsmall": "XS", "extra small": "XS", "extra-small": "XS",
    "s": "S", "sm": "S", "small": "S",
    "m": "M", "med": "M", "medium": "M",
    "l": "L", "lg": "L", "large": "L",
    "xl": "XL", "x-large": "XL", "xlarge": "XL", "extra large": "XL", "extra-large": "XL",
    "xxl": "XXL", "2xl": "XXL", "xx-large": "XXL", "xxlarge": "XXL", "extra extra large": "XXL",
    "double xl": "XXL",
}


def normalize_size(size: str) -> str | None:
    """Map what a shopper types ("medium", "2XL") onto the sizes in the database."""
    key = _norm(size).replace("_", " ")
    return SIZE_ALIASES.get(key) or (key.upper() if key.upper() in SIZE_ORDER else None)


# ---- Categories --------------------------------------------------------------------

CATEGORIES = ["Crewnecks & Sweatshirts", "Hoodies", "Jackets", "Long Sleeves", "Quarter-Zips", "T-Shirts"]

# Phrases a shopper might use for each category, checked in this order ("hooded sweatshirt"
# is a hoodie, so hoodies are checked before sweatshirts).
CATEGORY_PATTERNS = [
    ("T-Shirts", r"\bt-?shirts?\b|\btshirts?\b|\btees?\b"),
    ("Hoodies", r"\bhood(ie|ies|y|ed)?\b"),
    ("Quarter-Zips", r"\bquarter[- ]?zips?\b|\b1/4[- ]?zips?\b"),
    ("Jackets", r"\bjackets?\b"),
    ("Long Sleeves", r"\blong[- ]?sleeves?\b|\bperformance shirts?\b"),
    ("Crewnecks & Sweatshirts", r"\bcrew[- ]?necks?\b|\bsweatshirts?\b|\bsweaters?\b"),
]


def normalize_category(category: str) -> str | None:
    """Accept a category name or an everyday phrase for it ("tees", "hoodies")."""
    text = _norm(category).replace("t shirt", "t-shirt")
    for name in CATEGORIES:
        if text == name.lower():
            return name
    return detect_category(text)


def detect_category(message: str) -> str | None:
    text = _norm(message).replace("t shirt", "t-shirt")
    for name, pattern in CATEGORY_PATTERNS:
        if re.search(pattern, text):
            return name
    return None


PRICE_LIMIT = re.compile(r"\b(?:under|below|less than|cheaper than|up to|max(?:imum)?)\s*\$?\s*(\d+(?:\.\d+)?)", re.I)


def detect_max_price(message: str) -> float | None:
    m = PRICE_LIMIT.search(message)
    return float(m.group(1)) if m else None


# ---- Keyword scoring ----------------------------------------------------------------

STOPWORDS = {"a", "an", "the", "do", "you", "have", "any", "i", "me", "show", "want", "need",
             "looking", "for", "in", "of", "is", "are", "what", "some", "with", "and", "or",
             "to", "can", "please", "your", "got", "there", "which", "all", "sell", "carry",
             "offer", "see", "find", "get", "buy", "like", "would", "could", "under", "below",
             "less", "than", "cheaper", "up", "max", "kind", "type", "option", "style", "item",
             "thing", "stuff", "available", "shop", "store"}

# Words that only name a garment type. Inside a category search they add nothing, so
# they're dropped, leaving the words that actually narrow the results (color, sport...).
GARMENT_WORDS = {"t-shirt", "tshirt", "shirt", "tee", "hoodie", "hoody", "hood", "hooded",
                 "crewneck", "crew", "neck", "sweatshirt", "sweater", "quarter-zip", "quarter",
                 "zip", "1/4", "jacket", "long", "sleeve", "long-sleeve", "performance",
                 "top", "clothe", "clothing", "apparel", "merch"}


def _keywords(message: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9-]+", message.lower()) if w not in STOPWORDS and len(w) > 1]
    # Loose singular forms so "hoodies" matches "hoodie".
    words = [w[:-1] if w.endswith("s") and len(w) > 3 else w for w in words]
    return [w for w in words if w not in STOPWORDS and not re.fullmatch(r"\d+(\.\d+)?", w)]


def _score_products(message: str, products: list[dict], limit: int = MAX_RESULTS,
                    words: list[str] | None = None) -> list[dict]:
    words = _keywords(message) if words is None else words
    if not words:
        return []
    scored = []
    for p in products:
        haystack = " ".join([p["name"], p["garment_type"], p["category"], p["description"],
                             *p["colors"], *p["search_tags"]]).lower()
        score = sum(1 for w in words if w in haystack)
        if score:
            scored.append((score, p))
    # Best match first, then in-stock items before sold-out ones, then A-Z.
    scored.sort(key=lambda s: (-s[0], s[1]["total_stock"] == 0, s[1]["name"]))
    return [p for _, p in scored[:limit]]


def _search(query: str, category: str | None, max_price: float | None) -> tuple[list[dict], int]:
    """Return (matches to show, total number of matches) for a catalogue search."""
    products = _all_products()
    if category:
        products = [p for p in products if p["category"] == category]
    if max_price is not None:
        products = [p for p in products if p["price"] <= max_price]
    words = _keywords(query)
    if category:
        words = [w for w in words if w not in GARMENT_WORDS]
    if words:
        matches = _score_products(query, products, limit=len(products), words=words)
    elif category or max_price is not None:
        # "What t-shirts do you have?" -> every product in the category (or budget).
        matches = sorted(products, key=lambda p: (p["total_stock"] == 0, p["name"]))
    else:
        matches = []
    return matches[:MAX_RESULTS], len(matches)


def _resolve(query: str) -> dict | ProductNotFound:
    """Find exactly one product by id or name; otherwise return suggestions, never a guess."""
    products = _all_products()
    q = _norm(query)
    for p in products:
        if p["product_id"] == query.strip() or _norm(p["product_id"]) == q:
            return p
    exact = [p for p in products if _norm(p["name"]) == q]
    if len(exact) == 1:
        return exact[0]
    partial = [p for p in products if q and q in _norm(p["name"])]
    if len(partial) == 1:
        return partial[0]
    candidates = (exact or partial or _score_products(query, products))[:5]
    if candidates:
        message = (f"No single product matches '{query}'. Ask the shopper which one they mean, "
                   f"or look one up by its product_id.")
    else:
        message = f"No product in the catalogue matches '{query}'."
    return ProductNotFound(query=query, message=message, suggestions=[_match(p) for p in candidates])


# ---- Agent tools -----------------------------------------------------------------

async def search_products(
    ctx: RunContext[ChatDeps],
    query: str = "",
    category: str | None = None,
    max_price: float | None = None,
) -> ProductSearchResult:
    """Search the catalogue for products matching a shopper's request.

    Use this whenever a shopper browses for a type of item ("what t-shirts do you have?",
    "gray hoodies", "hockey gear", "jackets under $90"). Pass `category` when they name a
    type of garment: you then get every matching item in that category, not just a few.
    Results include each product's product_id; put the ids you want shown on the website
    in your reply's product_ids.

    Args:
        query: Words that narrow the search, such as a color, sport, team, or style. Can be empty.
        category: Optional category: T-Shirts, Hoodies, Crewnecks & Sweatshirts, Quarter-Zips,
            Jackets, or Long Sleeves. Everyday names like "tees" also work.
        max_price: Optional price ceiling in US dollars, for requests like "under $50".
    """
    resolved = None
    if category:
        resolved = normalize_category(category)
        if resolved is None:
            return ProductSearchResult(
                query=query, category=category, max_price=max_price, total_matches=0, matches=[],
                message=f"'{category}' isn't a category. Categories: {', '.join(CATEGORIES)}.",
            )
    matches, total = _search(query, resolved, max_price)
    ctx.deps.record(matches)
    ctx.deps.searches.append((" ".join(x for x in [resolved or "", query] if x) or "all items", total))
    if not matches:
        message = "No products matched that search."
    elif total > len(matches):
        message = f"Found {total} matching products; showing the first {len(matches)}."
    else:
        message = f"Found {total} matching products."
    return ProductSearchResult(
        query=query, category=resolved, max_price=max_price, total_matches=total,
        matches=[_match(p) for p in matches], message=message,
    )


async def get_product_description(ctx: RunContext[ChatDeps], product: str) -> ProductDescriptionResult | ProductNotFound:
    """Get a product's full description, garment type, category, and colors from the database.

    Args:
        product: The product_id (preferred) or the product's exact name.
    """
    found = _resolve(product)
    if isinstance(found, ProductNotFound):
        return found
    ctx.deps.record([found])
    return ProductDescriptionResult(
        product_id=found["product_id"], name=found["name"], garment_type=found["garment_type"],
        category=found["category"], description=found["description"], colors=found["colors"],
    )


async def get_product_price(ctx: RunContext[ChatDeps], product: str) -> PriceResult | ProductNotFound:
    """Get a product's exact price from the database. Use this for every price question.

    Args:
        product: The product_id (preferred) or the product's exact name.
    """
    found = _resolve(product)
    if isinstance(found, ProductNotFound):
        return found
    ctx.deps.record([found])
    return price_of(found)


def price_of(found: dict) -> PriceResult:
    return PriceResult(
        product_id=found["product_id"], name=found["name"],
        price=found["price"], price_display=f"${found['price']:.2f}",
    )


async def get_product_stock(
    ctx: RunContext[ChatDeps], product: str, size: str | None = None
) -> StockResult | ProductNotFound:
    """Get how many of a product are in stock, for one size or for every size, from the database.

    Use this for every stock, availability, or size question. Pass `size` when the shopper
    asks about a particular size; leave it out to get the count for every size.

    Args:
        product: The product_id (preferred) or the product's exact name.
        size: Optional size the shopper asked about, e.g. "M", "medium", "XL", or "2XL".
    """
    found = _resolve(product)
    if isinstance(found, ProductNotFound):
        return found
    ctx.deps.record([found])
    return stock_of(found, size)


def stock_of(found: dict, size: str | None = None) -> StockResult:
    name = found["name"]
    sizes = [SizeAvailability(size=i["size"], quantity=i["quantity"], status=_status(i["quantity"]))
             for i in found["inventory"]]
    in_stock = [s.size for s in sizes if s.quantity > 0]
    out_of_stock = [s.size for s in sizes if s.quantity == 0]
    total = found["total_stock"]

    requested = None
    if size is not None:
        wanted = normalize_size(size)
        requested = next((s for s in sizes if s.size == wanted), None)
        if requested is None:
            message = f"{name} doesn't come in size '{size}'. Sizes offered: {', '.join(s.size for s in sizes)}."
        elif requested.quantity == 0:
            others = f" In-stock sizes: {', '.join(in_stock)}." if in_stock else " It is sold out in every size."
            message = f"{name} is out of stock in size {requested.size}.{others}"
        else:
            low = " That is low stock." if requested.status == "low_stock" else ""
            message = f"{name} has {requested.quantity} in stock in size {requested.size}.{low}"
    elif total == 0:
        message = f"{name} is out of stock in every size."
    else:
        per_size = "; ".join(f"{s.size}: {s.quantity}" for s in sizes)
        sold_out = f" Out of stock in: {', '.join(out_of_stock)}." if out_of_stock else ""
        message = f"{name} has {total} in stock in total ({per_size}).{sold_out}"

    return StockResult(
        product_id=found["product_id"], name=name, size_requested=size, requested_size=requested,
        sizes=sizes, in_stock_sizes=in_stock, out_of_stock_sizes=out_of_stock,
        total_stock=total, status=_status(total), message=message,
    )


async def list_categories(ctx: RunContext[ChatDeps]) -> str:
    """List the product categories the shop carries, with how many styles are in each."""
    counts: dict[str, int] = {}
    for p in _all_products():
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    return "Categories: " + "; ".join(f"{name} ({n} styles)" for name, n in sorted(counts.items()))


# ---- Who is chatting, and what page they're on ---------------------------------------

async def get_customer_profile(ctx: RunContext[ChatDeps]) -> CustomerProfile:
    """Get the signed-in shopper's own account details: name, email, when they joined, and
    their recent saved conversations. Returns signed_in=false for guests.

    Use this when the shopper asks about themselves or their account ("what's my email?",
    "what did I ask about last time?"). It only ever returns the shopper who is chatting.
    """
    c = ctx.deps.customer
    if c is None:
        return CustomerProfile(
            signed_in=False,
            message="The shopper is not signed in. Their chat isn't saved; they can log in or create an account to save it.",
        )
    conversations = chat_store.list_conversations(c.user_id)
    return CustomerProfile(
        signed_in=True, first_name=c.first_name, last_name=c.last_name, name=c.name, email=c.email,
        member_since=c.member_since, saved_conversations=len(conversations),
        recent_conversations=conversations[:5],
        message=f"{c.name} ({c.email}) is signed in and has {len(conversations)} saved conversation(s).",
    )


def _page_product(p: dict, position: int | None = None) -> PageProduct:
    return PageProduct(position=position, product_id=p["product_id"], name=p["name"], category=p["category"])


def read_page(deps: ChatDeps) -> PageContextResult:
    """Turn the page context the website sent into database facts (unknown ids are dropped)."""
    page = deps.page or PageContext()
    catalogue = {p["product_id"]: p for p in _all_products()}
    viewing = catalogue.get(page.product_id) if page.product_id else None
    on_page = [catalogue[i] for i in (page.results.product_ids if page.results else []) if i in catalogue]
    deps.record(([viewing] if viewing else []) + on_page)  # so the agent can show them as cards

    parts = []
    if viewing:
        parts.append(f"The shopper is on the product page for {viewing['name']} (product_id {viewing['product_id']}).")
    else:
        parts.append(f"The shopper is on the {page.page} page ({page.path}).")
    if page.category:
        parts.append(f"The Products page is filtered to {page.category}.")
    if on_page:
        parts.append(f"A results grid with {len(on_page)} products is showing, listed in order.")
    return PageContextResult(
        page=page.page, path=page.path,
        viewing_product=_page_product(viewing) if viewing else None,
        category_filter=page.category,
        results_title=page.results.title if page.results and on_page else None,
        results_on_page=[_page_product(p, i + 1) for i, p in enumerate(on_page)],
        message=" ".join(parts),
    )


async def get_page_context(ctx: RunContext[ChatDeps]) -> PageContextResult:
    """Find out what the shopper is looking at: the product page they're on, the Products page
    category filter, and the products in any results grid on the page (in order).

    Use this when the shopper refers to something on screen: "this", "this one", "it",
    "the hoodie I'm looking at", "the second one", "the gray one in the results". Then use the
    product_id with get_product_price, get_product_stock, or get_product_description.
    """
    return read_page(ctx.deps)


def describe_context(deps: ChatDeps) -> str:
    """Short per-request instructions for the agent: who is chatting and where they are.

    Built only from the database (the shopper's session and product rows), never from text
    typed in the browser.
    """
    lines = []
    c = deps.customer
    if c:
        first = c.first_name or c.name.split(" ")[0]
        lines.append(
            f"The shopper is signed in as {c.name} ({c.email}), a customer since {c.member_since}. "
            f"Greet them by first name ({first}). This conversation is saved to their account."
        )
    else:
        lines.append("The shopper is a guest (not signed in). This conversation is not saved.")
    if deps.page:
        page = read_page(deps)
        lines.append(page.message + " Call get_page_context when they refer to something on screen.")
    return "\n".join(lines)


# ---- Plain-text catalogue search (search bar + no-LLM fallback) ------------------

def catalogue_search(message: str) -> SearchResponse:
    """Search the way a shopper types: spot the category and any price limit, then match keywords.

    Used by the website's search bar (GET /api/search) and by the chat's no-LLM fallback, so both
    find the same products the agent's search_products tool would.
    """
    category = detect_category(message)
    max_price = detect_max_price(message)
    matches, total = _search(message, category, max_price)
    title = None
    if matches:
        words = PRICE_LIMIT.sub("", message).strip(" ,.?!")  # "hockey under $50" -> "hockey"
        title = category or (f"Matches for \u201c{words[:40]}\u201d" if _keywords(words) else "All items")
        if max_price is not None:
            title += f" under ${max_price:g}"
    return SearchResponse(
        query=message, category=category, max_price=max_price, results_title=title,
        total_matches=total, products=[ProductCard(**p) for p in matches],
    )


SIZE_WORDS = re.compile(r"\b(extra[- ]small|x-small|xs|small|medium|large|extra[- ]large|x-large|xx-large|xxl|2xl|xl)\b", re.I)
SIZE_LETTER = re.compile(r"\b(?:size|in|in a|in an)\s+(s|m|l)\b", re.I)  # "in m", not the m in "I'm"
PRICE_Q = re.compile(r"\b(price|cost|costs|how much|expensive|cheap)\b|\$", re.I)
STOCK_Q = re.compile(r"\b(stock|available|availability|left|sizes?|sold out|have (it|this|one|any))\b", re.I)
ABOUT_Q = re.compile(r"\b(describe|description|tell me (more )?about|what is (it|this)|made of|material|colou?rs?|look like)\b", re.I)
POINTING = re.compile(r"\b(this|it|that|this one|that one)\b", re.I)
IDENTITY_Q = re.compile(r"\b(who am i|my name|my email|my account|am i (logged|signed) in)\b", re.I)
GREETING_Q = re.compile(r"^\s*(hi|hey|hello|yo|hiya|howdy|good (morning|afternoon|evening))( there)?[\s!.,]*$", re.I)


def _size_in(message: str) -> str | None:
    m = SIZE_WORDS.search(message) or SIZE_LETTER.search(message)
    return normalize_size(m.group(1)) if m else None


def keyword_fallback(message: str, deps: ChatDeps | None = None) -> ChatResponse:
    """Reply without the LLM (used when no API key is configured or the model errors).

    Follows the same contract as the agent (a reply, an optional results title, and product
    cards from the database), and uses the same dependencies: it greets a signed-in shopper by
    name and answers price, stock, and size questions about the product page they're on.
    """
    deps = deps or ChatDeps()
    c = deps.customer
    first = (c.first_name or c.name.split(" ")[0]) if c else None

    if GREETING_Q.match(message):
        hello = f"Hi {first}!" if first else "Hi there!"
        return ChatResponse(reply=f"{hello} 👋 Ask me about products, colors, sizes, or prices.")
    if IDENTITY_Q.search(message):
        deps.note("get_customer_profile", {}, {"signed_in": c is not None})
        if c:
            return ChatResponse(reply=f"You're signed in as {c.name} ({c.email}). Your chats are saved to your account.")
        return ChatResponse(reply="You're not signed in right now. Log in or create an account to save your chats.")

    # Questions about the product page the shopper is on ("is this in medium?", "how much is it?").
    viewing = read_page(deps).viewing_product if deps.page else None
    if viewing and (POINTING.search(message) or not detect_category(message)):
        product = deps.seen[viewing.product_id]
        size = _size_in(message)
        wants_price, wants_about = PRICE_Q.search(message), ABOUT_Q.search(message)
        wants_stock = size or STOCK_Q.search(message)
        if wants_price or wants_stock or wants_about:
            pid = product["product_id"]
            deps.note("get_page_context", {}, {"page": deps.page.page, "viewing_product": pid})
            parts = []
            if wants_about:
                parts.append(product["description"])
                deps.note("get_product_description", {"product": pid}, product["description"])
            if wants_price:
                price = price_of(product)
                parts.append(f"The {product['name']} is {price.price_display}.")
                deps.note("get_product_price", {"product": pid}, price)
            if wants_stock:
                stock = stock_of(product, size)
                parts.append(stock.message)
                deps.note("get_product_stock", {"product": pid, "size": size}, stock.message)
            return ChatResponse(reply=" ".join(parts), products=[ProductCard(**product)])

    found = catalogue_search(message)
    deps.searches.append((message, found.total_matches))
    deps.note("search_products", {"query": message, "category": found.category, "max_price": found.max_price},
              {"total_matches": found.total_matches, "shown": len(found.products)})
    if not found.products:
        what = found.category.lower() if found.category else "anything"
        return ChatResponse(
            reply=f"I couldn't find {what} matching that. Try a garment type (hoodie, crewneck, "
            "T-shirt), a color, or a team — or ask about sizes and prices.",
            products=[],
        )
    shown, total = len(found.products), found.total_matches
    more = f" (showing the first {shown})" if total > shown else ""
    kind = found.category.lower() if found.category else "matching items"
    reply = f"We have {total} {kind}{more}. I've put them on the page for you. Click any one for full details."
    return ChatResponse(reply=reply, results_title=found.results_title, products=found.products)
