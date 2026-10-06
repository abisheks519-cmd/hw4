"""Pydantic types shared by the chat API and the PydanticAI agent.

These describe the shapes that cross the wire between the front-end chat widget and
FastAPI: the incoming message and the outgoing reply plus product cards.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SizeStock(BaseModel):
    size: str
    quantity: int


class ProductCard(BaseModel):
    """One product as shown in the chat (and on the product pages)."""

    product_id: str
    name: str
    garment_type: str
    category: str
    description: str
    short_description: str
    colors: list[str]
    search_tags: list[str]
    image_url: str  # compressed WebP (product page size)
    thumb_url: str  # smaller WebP for cards and thumbnails
    original_image_url: str  # the original JPEG
    cutout_url: str | None = None  # product with the photo background removed (transparent WebP)
    cutout_thumb_url: str | None = None
    price: float
    inventory: list[SizeStock]
    total_stock: int
    material: str | None = None  # fabric named in the catalogue, if any (for Compare)
    features: list[str] = []
    sleeve: str | None = None


# ---- Tool lookup results -------------------------------------------------------------
# What the agent's tools return. Every value is copied straight from campus_customs.db;
# the `message` fields are sentences built in code from those values, so the model can
# repeat them without doing any arithmetic or guessing of its own.

StockStatus = Literal["in_stock", "low_stock", "out_of_stock"]


class ProductMatch(BaseModel):
    """A short catalogue entry, used in search results and "did you mean" suggestions."""

    product_id: str
    name: str
    category: str
    price: float
    total_stock: int


class ProductSearchResult(BaseModel):
    query: str
    category: str | None = None
    max_price: float | None = None
    total_matches: int
    matches: list[ProductMatch]
    message: str


class ProductNotFound(BaseModel):
    """Returned when a lookup can't be tied to exactly one product."""

    query: str
    message: str
    suggestions: list[ProductMatch] = Field(default_factory=list)


class ProductDescriptionResult(BaseModel):
    product_id: str
    name: str
    garment_type: str
    category: str
    description: str
    colors: list[str]


class PriceResult(BaseModel):
    product_id: str
    name: str
    price: float
    price_display: str
    currency: Literal["USD"] = "USD"


class SizeAvailability(BaseModel):
    size: str
    quantity: int
    status: StockStatus


class StockResult(BaseModel):
    product_id: str
    name: str
    size_requested: str | None
    requested_size: SizeAvailability | None
    sizes: list[SizeAvailability]
    in_stock_sizes: list[str]
    out_of_stock_sizes: list[str]
    total_stock: int
    status: StockStatus
    message: str


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


# ---- Who is chatting, and what page they're on --------------------------------------

class CustomerContext(BaseModel):
    """The signed-in shopper, as the agent sees them (from the users table, via their session)."""

    user_id: int
    first_name: str | None
    last_name: str | None
    name: str
    email: str
    member_since: str  # date the account was created


PageName = Literal[
    "home", "products", "product", "about", "login", "create-account", "logout",
    "cart", "checkout", "order", "compare", "admin", "other",
]


class ResultsOnPage(BaseModel):
    title: str = Field(max_length=120)
    product_ids: list[str] = Field(default_factory=list, max_length=30)


class PageContext(BaseModel):
    """What the shopper is looking at when they send a message. Sent by the website.

    Only ids and the page type come from the browser; product names and details are looked
    up in the database on the server.
    """

    path: str = Field(default="/", max_length=200)
    page: PageName = "other"
    product_id: str | None = Field(default=None, max_length=120)  # set on a product page
    category: str | None = Field(default=None, max_length=60)  # Products page category filter
    results: ResultsOnPage | None = None  # the results grid showing on the page, if any


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    # Signed-in shoppers: which saved conversation this message belongs to (None starts a new one).
    conversation_id: int | None = None
    # Guests only: prior turns so the agent has context. Signed-in history comes from the database.
    # Capped so a browser can't send an oversized conversation (only the last 12 turns are used).
    history: list[ChatTurn] = Field(default_factory=list, max_length=40)
    page_context: PageContext | None = None

    @field_validator("history")
    @classmethod
    def shorten_turns(cls, turns: list[ChatTurn]) -> list[ChatTurn]:
        return [ChatTurn(role=t.role, content=t.content[:2000]) for t in turns]


class SearchResponse(BaseModel):
    """What GET /api/search returns to the website's search bar."""

    query: str
    category: str | None = None
    max_price: float | None = None
    results_title: str | None = None
    total_matches: int
    products: list[ProductCard] = Field(default_factory=list)


# ---- The chat API contract -----------------------------------------------------------

class AgentReply(BaseModel):
    """The agent's structured answer: its chat message plus which products the website should show."""

    reply: str = Field(description="Your chat message to the shopper. Short and friendly.")
    results_title: str | None = Field(
        default=None,
        description=(
            "A short heading for a set of matching products shown on the website, e.g. 'T-Shirts' or "
            "'Gray hoodies under $70'. Set it when the shopper is browsing for a type of item. "
            "Leave it null for questions about one specific product."
        ),
    )
    product_ids: list[str] = Field(
        default_factory=list,
        description=(
            "The product_id of every product to show as a card, in display order. "
            "Only use product_ids returned by your tools in this conversation."
        ),
    )


class ChatResponse(BaseModel):
    """What POST /api/chat returns to the website.

    `products` are filled in by the server from the database (never from the model's text).
    When `results_title` is set, the website shows `products` as a results grid on the page.
    """

    reply: str
    results_title: str | None = None
    products: list[ProductCard] = Field(default_factory=list)
    # Set for signed-in shoppers: the saved conversation this exchange was stored in.
    conversation_id: int | None = None
    conversation_title: str | None = None


# ---- Saved chat history (signed-in shoppers) ------------------------------------------

class ConversationSummary(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int


class StoredMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    results_title: str | None = None
    products: list[ProductCard] = Field(default_factory=list)
    created_at: str


class ConversationDetail(ConversationSummary):
    messages: list[StoredMessage]


# ---- Tool results about the shopper and the page -------------------------------------

class CustomerProfile(BaseModel):
    """What get_customer_profile returns."""

    signed_in: bool
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None
    email: str | None = None
    member_since: str | None = None
    saved_conversations: int = 0
    recent_conversations: list[ConversationSummary] = Field(default_factory=list)
    message: str


class PageProduct(BaseModel):
    position: int | None = None  # 1-based position in the results grid
    product_id: str
    name: str
    category: str


class PageContextResult(BaseModel):
    """What get_page_context returns: the page, and which products are on it, from the database."""

    page: PageName
    path: str
    viewing_product: PageProduct | None = None
    category_filter: str | None = None
    results_title: str | None = None
    results_on_page: list[PageProduct] = Field(default_factory=list)
    message: str


# ---- Cart and checkout (Problem 9) -------------------------------------------------------
# Prices and stock in a cart always come from the database when the cart is read; the website
# only ever sends product ids, sizes, and quantities.

class CartItemIn(BaseModel):
    product_id: str = Field(min_length=1, max_length=120)
    size: str = Field(min_length=1, max_length=5)
    quantity: int = Field(default=1, ge=0, le=20)


class CartLine(BaseModel):
    product_id: str
    name: str
    category: str
    size: str
    quantity: int
    unit_price: float
    line_total: float
    thumb_url: str
    available: int  # how many are in stock in this size right now
    warning: str | None = None  # e.g. "Only 2 left in M; quantity reduced"


class CartOut(BaseModel):
    items: list[CartLine]
    item_count: int
    subtotal: float
    shipping: float
    tax: float
    total: float
    free_shipping_at: float
    free_shipping_remaining: float
    tax_rate: float
    saved_to_account: bool  # signed in: the cart is saved to their account


class OrderLine(BaseModel):
    product_id: str
    name: str
    size: str
    quantity: int
    unit_price: float
    line_total: float
    thumb_url: str | None = None


class OrderOut(BaseModel):
    order_number: str
    created_at: str
    full_name: str
    email: str
    phone: str
    ship_to: str
    card: str  # "Visa ending in 4242" (the full number is never stored)
    items: list[OrderLine]
    item_count: int
    subtotal: float
    shipping: float
    tax: float
    total: float
