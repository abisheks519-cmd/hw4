# Campus Customs — Storefront

React + Vite + TypeScript frontend (`frontend/`) with a FastAPI backend (`backend/`) that reads `campus_customs.db`, serves product images from `products/`, and runs the shop chatbot as a PydanticAI agent.

## Project layout

```
hw4/
├── AI_prompts.md            # prompts used for each problem
├── requirements.txt         # backend Python packages
├── .env.example             # copy to .env and add ANTHROPIC_API_KEY
├── .gitignore
├── README.md
├── frontend/                # Vite React TypeScript app
├── backend/
│   ├── main.py              # FastAPI app — run with: uvicorn main:app --reload --port 8000
│   ├── agent.py             # PydanticAI agent: prompt + model + tools, agent loop, audit trail
│   ├── models.py            # Pydantic types
│   ├── tools.py             # agent tools (+ no-key keyword fallback)
│   ├── prompts/
│   │   └── prompt.md        # system prompt and safety rules
│   └── …                    # supporting modules: db, auth, chat_store, shop, validation,
│                            #   analytics, images, audit, db_viewer
└── output/
    ├── harness.md
    ├── design.md
    ├── usability.md
    ├── app_check.html
    ├── app_check_images/    # screenshots linked from app_check.html
    └── audit_trail.json     # append-only agent-loop log
```

**Local-only data pack (not in git):** `campus_customs.db`, the `products/` photos (including the generated `products/optimized/` images), and `campus_customs_db.html` (a generated database snapshot that includes password hashes). Keep them in the top-level folder next to `backend/` and `frontend/`; `.gitignore` leaves them out of the repository, along with `.env`, `backend/.venv/`, `frontend/node_modules/`, and `frontend/dist/`.

## Run it

Open two terminals.

**1. API (port 8000)** — run from the `backend/` folder:
```bash
cd backend
python3 -m venv .venv                  # first time only
.venv/bin/pip install -r ../requirements.txt   # first time only (and after Problem 9: adds Pillow)
.venv/bin/uvicorn main:app --reload --port 8000
```

**2. Frontend (port 5173)**
```bash
cd frontend
npm install        # first time only
npm run dev
```

Then open http://localhost:5173. Vite forwards `/api` and `/media` requests to the API.

## Chatbot API key

The chat assistant is a PydanticAI agent that calls an Anthropic Claude model. To enable it, copy `.env.example` (top-level folder) to `.env` and add your `ANTHROPIC_API_KEY`. Without a key the chat widget still works, using a simple keyword search over the catalogue. `GET /api/health` shows which mode is active.

## Pages
| Route | Page |
|---|---|
| `/` | Home: welcome hero, shop by category, featured products |
| `/products` | All products with category filters, search, and sorting |
| `/products/:productId` | Single product: large image, description, price, colors, stock by size |
| `/about` | About Us: brand story and values |
| `/login`, `/create-account` | Account forms, checked field by field against the server's validation rules |
| `/cart` | The cart: quantities, subtotal, shipping, tax, total (saved to your account when signed in) |
| `/checkout` | Contact, shipping, and payment form (demo, no card is charged), then `/order/:orderNumber` confirmation |
| `/compare` | Up to 4 products side by side: price, type, colors, material, features, sizes |
| `/admin` | Analytics dashboard (admins only, e.g. the test account) |

The floating chat assistant (bottom right), the cart drawer, breadcrumbs, and the compare tray are on every page. See `output/usability.md` for the Problem 9 features and `output/design.md` for the storefront design (Problem 10). Fonts are self-hosted npm packages, so run `npm install` after pulling.

## API
| Endpoint | Returns |
|---|---|
| `GET /api/products` | All products with inventory and total stock |
| `GET /api/products/{product_id}` | One product (404 if missing) |
| `GET /api/categories` | Product categories with counts |
| `GET /api/search?q=...` | Search bar: same catalogue search the assistant uses → `{ results_title, total_matches, products }` |
| `GET /api/health` | Status plus which chat mode is active (`llm` or `keyword-fallback`) |
| `POST /api/chat` | `{ message, conversation_id, history, page_context }` → `{ reply, results_title, products, conversation_id, conversation_title }`. Signed-in shoppers' chats are saved; with a `results_title`, the site shows the products as a results grid on the page |
| `GET /api/chats` | The signed-in shopper's saved conversations (401 for guests) |
| `GET /api/chats/{id}` | One saved conversation with its messages (404 if it isn't yours) |
| `DELETE /api/chats/{id}` | Delete one of your saved conversations |
| `POST /api/auth/signup` | Create an account (first/last name, email, password, confirm); stores a securely hashed password in `users` |
| `POST /api/auth/login` | Log in with email + password; starts a session (HttpOnly cookie) |
| `GET /api/auth/me` | The signed-in shopper, or `null` |
| `POST /api/auth/logout` | End the session |
| `GET/POST/PATCH/DELETE /api/cart…` | The cart (see `output/harness.md` §9) |
| `POST /api/checkout`, `GET /api/orders/{number}` | Place an order, view its receipt |
| `POST /api/validate/{form}` | Live form validation (`signup`, `login`, `checkout`) |
| `POST /api/events` | Analytics events from the browser |
| `GET /api/admin/analytics?days=30` | Admin dashboard data (admins only) |
| `GET /media/products/{file}.jpg` | Product images (originals) |
| `GET /media/products/optimized/{file}-480.webp`, `-320.webp` | Compressed product images (made at startup by `images.py`) |

### Backend layout
| File | Role |
|---|---|
| `backend/main.py` | FastAPI app: product, category, auth, and chat routes; serves images |
| `backend/db.py` | Read-only access to `campus_customs.db`, product shaping, and the in-memory catalogue cache |
| `backend/shop.py` | Cart, checkout, and orders |
| `backend/validation.py` | Form validation rules (names, email, phone, address, card) |
| `backend/analytics.py` | Event tracking, admin access, and the analytics dashboard |
| `backend/images.py` | Makes compressed WebP copies of product photos, plus background-free cutouts for the storefront design (the first run takes a few minutes, in the background) |
| `backend/db_viewer.py` | Refreshes `campus_customs_db.html` (the browsable database snapshot) from the live database: `python db_viewer.py` |
| `backend/audit.py` | Appends every step of the chat agent loop (model responses, tool calls and results, stop reasons) to `output/audit_trail.json`; never cleared |
| `backend/auth.py` | Account signup/login with securely hashed passwords, and login sessions |
| `backend/chat_store.py` | Saved chat history for signed-in shoppers (`chat_conversations` + `chat_messages`) |
| `backend/agent.py` | Loads the PydanticAI shop agent (prompt file + model) |
| `backend/tools.py` | Tools the agent calls to search the catalogue (+ keyword fallback) |
| `backend/models.py` | Pydantic types for chat requests, replies, and product cards |
| `backend/prompts/prompt.md` | The agent's system prompt (voice + safety) |

Password hashing, the login flow, and the chatbot architecture are documented in `output/harness.md`.
