"""Campus Customs API — products, images, accounts, and the shop chatbot.

Run from the backend/ folder:
    uvicorn main:app --reload --port 8000
"""

import secrets
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

import analytics
import chat_store
import images
import shop
import validation
from agent import agent_status, run_chat
from auth import get_customer, init_session_storage, require_customer
from auth import router as auth_router
from db import PRODUCTS_DIR, cached_product, cached_products, catalogue_version, invalidate_products
from models import ChatRequest, ChatResponse, ConversationDetail, ConversationSummary, CustomerContext, SearchResponse
from tools import catalogue_search

VISITOR_COOKIE = "cc_visitor"
IMAGE_CACHE_SECONDS = 7 * 86400


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create any tables this database doesn't have yet (sessions, chats, carts/orders, analytics).
    init_session_storage()
    chat_store.init_chat_storage()
    shop.init_shop_storage()
    analytics.init_analytics_storage()
    cached_products()  # warm the catalogue cache so the first shopper doesn't wait

    def prepare_images():
        # Compressed WebP copies and background-free cutouts (only new/changed photos; the first
        # run takes a few minutes). Runs in the background so the API starts right away, then
        # refreshes the catalogue so the new image URLs are used.
        images.optimize_all()
        invalidate_products()

    threading.Thread(target=prepare_images, daemon=True).start()
    yield


class CachedImages(StaticFiles):
    """Product photos, with a Cache-Control header so browsers keep them instead of re-downloading."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = f"public, max-age={IMAGE_CACHE_SECONDS}"
        return response


app = FastAPI(title="Campus Customs API", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)  # compress JSON (the product list shrinks ~90%)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.add_exception_handler(RequestValidationError, validation.validation_error_handler)
app.include_router(auth_router)
app.include_router(shop.router)
app.include_router(validation.router)
app.include_router(analytics.router)
app.include_router(analytics.admin_router)
# Product photos: /media/products/<file>.jpg originals, /media/products/optimized/<file>-480.webp etc.
app.mount("/media/products", CachedImages(directory=PRODUCTS_DIR), name="product-images")


@app.middleware("http")
async def visitor_id(request: Request, call_next):
    """Give every browser an anonymous id (HttpOnly cookie) for guest carts and analytics."""
    vid = request.cookies.get(VISITOR_COOKIE)
    new = not vid or len(vid) > 64
    if new:
        vid = secrets.token_urlsafe(16)
    request.state.visitor_id = vid
    response = await call_next(request)
    if new and request.url.path.startswith("/api/"):
        response.set_cookie(VISITOR_COOKIE, vid, max_age=365 * 86400, httponly=True, samesite="lax", path="/")
    return response


def _not_modified(request: Request, response: Response, tag: str) -> bool:
    """ETag support: the browser keeps the last response and we answer 304 if nothing changed."""
    response.headers["ETag"] = tag
    response.headers["Cache-Control"] = "no-cache"  # always check, but reuse the copy when unchanged
    return request.headers.get("if-none-match") == tag


@app.get("/api/health")
def health():
    return {"status": "ok", **agent_status()}


@app.get("/api/products")
def list_products(request: Request, response: Response):
    tag = f'"catalogue-{catalogue_version()}"'
    if _not_modified(request, response, tag):
        return Response(status_code=304, headers=dict(response.headers))
    return cached_products()


@app.get("/api/products/{product_id}")
def get_product(product_id: str, request: Request, response: Response):
    found = cached_product(product_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if _not_modified(request, response, f'"{product_id}-{catalogue_version()}"'):
        return Response(status_code=304, headers=dict(response.headers))
    return found


@app.get("/api/categories")
def list_categories():
    counts: dict[str, int] = {}
    for p in cached_products():
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    return [{"name": k, "count": v} for k, v in sorted(counts.items())]


@app.get("/api/search", response_model=SearchResponse)
def search(
    request: Request, q: str = Query(..., min_length=1, max_length=100),
    customer: CustomerContext | None = Depends(get_customer),
) -> SearchResponse:
    """The website's search bar: same catalogue search the chat assistant uses, without calling the AI."""
    result = catalogue_search(q)
    analytics.record_search(request, customer, q, result.total_matches, "search_bar")
    return result


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, customer: CustomerContext | None = Depends(get_customer)) -> ChatResponse:
    """Send a shopper's message to the PydanticAI agent and return its reply + product cards.

    Signed-in shoppers: the agent gets their saved conversation from the database, and the new
    question and reply are saved to it. Guests: nothing is saved.
    """
    saved_history = None
    if customer and req.conversation_id is not None:
        saved_history = chat_store.history_turns(customer.user_id, req.conversation_id)
        if saved_history is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    searches: list[tuple[str, int]] = []
    response = await run_chat(req, customer=customer, saved_history=saved_history, searches=searches)
    if searches:  # the assistant searched the catalogue: log the shopper's words for the dashboard
        analytics.record_search(request, customer, req.message, max(total for _, total in searches), "chat")
    if customer:
        response.conversation_id, response.conversation_title = chat_store.save_exchange(
            customer.user_id, req.conversation_id, req.message, response
        )
    return response


# ---- Saved chat history (signed-in shoppers only) ------------------------------------

@app.get("/api/chats", response_model=list[ConversationSummary])
def list_chats(customer: CustomerContext = Depends(require_customer)):
    return chat_store.list_conversations(customer.user_id)


@app.get("/api/chats/{conversation_id}", response_model=ConversationDetail)
def get_chat(conversation_id: int, customer: CustomerContext = Depends(require_customer)):
    found = chat_store.get_conversation(customer.user_id, conversation_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return found


@app.delete("/api/chats/{conversation_id}", status_code=204)
def delete_chat(conversation_id: int, customer: CustomerContext = Depends(require_customer)):
    if not chat_store.delete_conversation(customer.user_id, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
