# Campus Customs — Usability Improvements

Six improvements are now live on the website: three the shopper sees on the front end and three in the backend. For each one, this file says what it does, where to find it on the site, and how it helps a Campus Customs shopper or the business.

| # | Improvement | Side | Where to see it |
|---|---|---|---|
| 1 | Shopping cart and checkout, saved to the shopper's account | Front end | Cart button (🛍) in the header · **Add to cart** on any product page · `/cart` · `/checkout` |
| 2 | Compare items side by side | Front end | **Compare** box on every product card and product page · the tray at the bottom · `/compare` |
| 3 | Breadcrumbs showing where you are | Front end | The bar under the header on every page except Home |
| 4 | Fast page loading: compressed images, caching, faster database reads | Backend | Every page (product images, product list) |
| 5 | Form validation for email, phone, name, address, and payment | Backend | Create Account, Login, and Checkout forms |
| 6 | Admin analytics dashboard: searches, abandoned carts, checked-out items, popular products | Backend | **📊 Dashboard** in the header when signed in as an admin (`/admin`) |

---

## 1. Shopping cart and checkout (front end)

**What it does**
- On a product page, pick a size and a quantity, then press **Add to cart**. The button only allows sizes that are in stock and quantities up to the stock on hand (at most 10 per size).
- A cart drawer slides in to confirm the item was added. You can change quantities or remove items there, or open the full cart page.
- The cart page lists every item with its size, unit price, and line total. It shows how much more you need for free shipping (over $75), plus the subtotal, shipping, Connecticut sales tax (6.35%), and **total**.
- **Proceed to checkout** opens the Checkout page. It has contact, shipping address, and payment sections, with the order summary and **total** beside them. **Place order** shows an order confirmation page with an order number, what was bought, where it ships, and the total.
- **Saved to the account:** a signed-in shopper's cart is stored in the database. If they log out, the cart empties on that screen. When they log back in, on any device, their cart is back. If a guest adds items and then logs in, those items are added to their saved cart.

**Why it helps the shopper**
- They can collect several items and pay once, instead of treating each product page as a dead end.
- They see the full price, with shipping and tax, before they commit, so there are no surprises at payment.
- A cart saved to their account lets them start on a laptop and finish on their phone later.

**Why it helps the business**
- The cart is where sales happen. Without it the site can show products but can't sell them.
- The free-shipping progress bar ("Add $12.00 more for free shipping") encourages larger orders.
- Prices and stock are always re-read from the database, and stock is checked again at the moment of purchase. The shop can't sell an item it doesn't have or charge an outdated price. After an order, stock goes down automatically.
- Carts saved to accounts can be measured, so abandoned carts appear on the dashboard (see #6).

**Safe by design:** it's a demo checkout, so no card is ever charged. The card number is checked for format, and only the card brand and last 4 digits are stored. The full number and security code are never saved.

---

## 2. Compare items (front end)

**What it does**
- Every product card and product page has a **Compare** box. Tick up to 4 items. A tray at the bottom of the page shows the picks, and **Compare** opens a side-by-side table.
- The table compares **price** (with a "Lowest price" badge), **type of clothing**, **category**, **colors**, **material**, **sleeve length**, **features** (kangaroo pocket, full zip, stand collar, and so on), **sizes in stock** (green = plenty, amber = 5 or fewer, struck through = sold out), **total in stock** ("Most in stock" badge), and the **description**.
- **Highlight differences** shades the rows where the items differ. **Only show differences** hides the rows where they're the same.
- The picks are remembered in the browser. The chat assistant also knows which items are being compared, so a shopper can ask "which one is cheaper?" on the Compare page.

**Why it helps the shopper**
- Choosing between similar items (say, three gray quarter-zips) no longer means flipping between tabs and remembering prices. The trade-offs sit in one table.
- They see which sizes are available across all the options at once, before they fall for an item that's sold out in their size.

**Why it helps the business**
- Shoppers who can decide quickly are more likely to buy than to leave undecided.
- Each comparison is logged, so the dashboard shows how often shoppers compare items.

**Honesty note:** material comes only from what the catalogue actually says (fleece, tri-blend, double knit, heavyweight, performance fabric, cotton). For the 80 products whose listing doesn't name a fabric, the table says "Not listed in the catalogue" rather than guessing.

---

## 3. Breadcrumbs (front end)

**What it does:** a bar under the header shows where the shopper is and how they got there. Every step except the last is a link back:

| Page | Breadcrumb |
|---|---|
| Products | Home › Products |
| Products filtered to Hoodies | Home › Products › Hoodies |
| A product | Home › Products › Hoodies › Basic Hoodie Big Yale |
| Cart → Checkout → Confirmation | Home › Cart › Checkout › Order confirmed |
| Compare | Home › Products › Compare (3) |
| Dashboard | Home › Admin dashboard |

**Why it helps the shopper:** they always know where they are. One click jumps back up a level, for example from a hoodie to all Hoodies, without the Back button or starting over from the menu. This matters most for shoppers who land on a product page from the search bar or the chat assistant.

**Why it helps the business:** easy moves between related products keep shoppers browsing. The category step turns every product page into a way into more of the catalogue.

---

## 4. Fast page loading (backend)

| What was done | Before | After |
|---|---|---|
| **Compressed images.** Each product photo now has two WebP copies (`backend/images.py`): a 480px one for the product page and a 320px thumbnail for cards, the cart, and chat. Originals are kept. | 102 JPEGs, **3,603 KB** | Product page: **1,181 KB** (67% smaller). Cards: **600 KB** (83% smaller) |
| **Lazy image loading.** Card images load only when they scroll into view, and are decoded off the main thread. | Every image loaded up front | Only visible cards load |
| **Browser caching of images.** Images are sent with `Cache-Control: max-age=7 days`. | No caching header | Repeat visits reuse the images already downloaded |
| **Compressed API responses (gzip).** | Product list **90 KB**, uncompressed | Product list **11.7 KB** (87% smaller), even with the new compare fields |
| **"Not modified" answers (ETag).** When the browser already has the latest product list, the server answers with an empty 304. | Full list every time | **0 bytes, under 1 ms** |
| **In-memory catalogue cache** (`backend/db.py`). The catalogue and stock are read once and kept in memory. They refresh right after a purchase changes stock, and at least every 5 minutes. Product pages, search, the chat assistant, and carts all read from it. | 2 database queries on every request (~0.8 ms) | Read from memory (~0.1 µs) |
| **Shared catalogue on the website.** The product list is fetched once and shared by every page (for 60 seconds), not re-downloaded per page. | Each page fetched it again | One download per minute of browsing |
| **Smaller first download.** Checkout, Compare, Order confirmation, and the Dashboard are split into separate files that load only when opened. | — | About 28 KB kept out of the first page load |
| **Faster database queries.** Indexes on the new tables (cart items by cart; orders by date and by user; order items by order and by product; analytics events by type + date, by date, and by product). The dashboard gathers everything in a few indexed queries instead of one per product. | — | `EXPLAIN QUERY PLAN` confirms searches use `idx_events_type_time` |

**Why it helps the shopper:** pages and product grids appear sooner, especially on phones and slow campus Wi-Fi, and scrolling through 102 products doesn't stall while large photos download.

**Why it helps the business:** shoppers leave slow sites, so speed directly protects sales. Smaller images and cached responses also mean less bandwidth and server work per visitor, which lowers hosting costs as traffic grows.

---

## 5. Form validation (backend)

All rules live in one place (`backend/validation.py`) and are applied in two ways:
1. **As the shopper types.** When they leave a field, the website asks the server (`POST /api/validate/<form>`), and any problem appears in red under that field. Once they fix it, the message disappears.
2. **When the form is submitted.** The API checks everything again and rejects bad data with a message for each field, so bad data can't be saved even if someone bypasses the website.

| Field | Rule | Example message |
|---|---|---|
| First / last name | Required, letters with spaces, hyphens, or apostrophes, 50 characters max | "First name can only contain letters, spaces, hyphens, and apostrophes." |
| Full name / name on card | As above, plus both a first and a last name | "Please enter both a first and last name." |
| Email | Required, valid format (one @, a real-looking domain), stored in lowercase | "Please enter a valid email address, like you@yale.edu." |
| Password (new accounts) | 8–128 characters, at least one letter and one number; confirmation must match | "Password needs at least one letter and one number." / "Passwords don't match." |
| Phone | 10-digit US number (a leading 1 is fine); saved as (203) 555-0123 | "Phone number must have 10 digits, like (203) 555-0123." |
| Street address | 5–100 characters, must include a number and a street name | "Please enter a street address with a number and street name, like 149 Elm St." |
| City | Letters only | "Please enter a valid city name (letters only)." |
| State | A real 2-letter US state code (includes DC) | "Please use a 2-letter US state code, like CT." |
| ZIP code | 5 digits or ZIP+4 | "ZIP code must be 5 digits (or ZIP+4, like 06511-1234)." |
| Card number | Visa, Mastercard, Amex, or Discover. Right length for the brand, and it must pass the Luhn checksum real card numbers use | "That card number isn't valid. Please check for typos." |
| Expiration | MM/YY, month 01–12, not in the past | "This card has expired." |
| Security code (CVV) | Digits only: 4 for American Express, 3 for other cards | "The security code for Visa is 3 digits." |

**Why it helps the shopper:** mistakes are caught on the spot, next to the field, in plain language. Nobody gets through a whole checkout only to be rejected at the end, or has an order fail to arrive because of a mistyped ZIP code.

**Why it helps the business:** clean data means deliverable orders, reachable customers (valid emails and phone numbers), and fewer support tickets and returned packages. Checking on the server as well protects the database from bad or malicious input.

*Try it:* on Checkout, type `555-12` as the phone number or `4242 4242 4242 4241` as the card. The valid test card is `4242 4242 4242 4242`.

---

## 6. Admin analytics dashboard (backend)

**Who can see it:** admins only. The dashboard (`/admin`) and its data (`GET /api/admin/analytics`) require a signed-in account marked as an admin (`users.is_admin`). Guests get "Please log in" and ordinary shoppers get "admins only", both on the page and from the API. The test account **test@campuscustoms.yale.edu** is an admin; others can be added with the `ADMIN_EMAILS` setting. Once an admin is signed in, **📊 Dashboard** appears in the header.

**What is tracked** (in the `analytics_events` table). Shoppers are identified only by account id or an anonymous browser id.

| Event | When it's recorded |
|---|---|
| Search | Every header search-bar search and every chat question that searched the catalogue, with the words used and the number of results |
| Product view | A product page is opened (once per shopper per product every 30 minutes, so refreshes don't inflate counts) |
| Cart add / remove | Items added to or taken out of a cart: product, size, quantity, value |
| Checkout started | The checkout page is opened with items in the cart |
| Compare | 2+ products compared side by side |
| Order placed | An order goes through: order number, units, total |

**What the dashboard shows.** Choose **7 days**, **30 days**, **90 days**, or **All time**.

| Section | What's in it | Business question it answers |
|---|---|---|
| Headline numbers | Revenue, orders, average order value, conversion rate, abandoned carts ($ left in them), cart abandonment rate, searches (% that found nothing), product views, cart adds, comparisons | How is the shop doing? |
| Day by day chart | Revenue, orders, visitors, product views, searches, or cart adds per day (hover for each day) | Is it growing? Did the game-day promo work? |
| Shopper funnel | Unique shoppers who visited → viewed a product → added to cart → started checkout → ordered, with the % kept at each step | Where do shoppers drop off? |
| Popular products | Top 15 by views, cart adds, units sold, and revenue, with the view-to-cart rate and current stock | What to feature, reorder, or promote |
| Top searches | What shoppers type, how often, average results, search bar vs. chat | What shoppers are looking for |
| Searches that found nothing | Searches with zero results (e.g. "socks", "baseball cap") | Products to add to the catalogue |
| Abandoned carts | Carts with items and no activity for 30+ minutes: shopper (name and email if signed in), items, value at today's prices, how long idle. **View items** shows what's inside | Who to remind, and how much revenue is being left behind |
| Checked-out items | Every product and size that sold, with units, orders, and revenue | What actually sells, down to the size |
| Sales by category and sizes sold | Revenue share by category, units by size | How to plan inventory |
| Recent orders | Latest orders: number, customer, items, ship-to city, total | Day-to-day order monitoring |
| Low stock alerts | Every size with 5 or fewer left, or sold out | What to restock before it sells out |

**Why it helps the business:** it turns shopper behavior into decisions. Restock what's popular and running low, add what shoppers search for but can't find, follow up on abandoned carts, and see which step of the funnel loses the most people. The data is limited to admins, so customer names, emails, and orders aren't exposed to other shoppers.

**Why it helps the shopper (indirectly):** a shop that watches failed searches and low stock carries more of what shoppers want, in their sizes.

**Sample data:** a brand-new shop has little activity, so an admin can press **Load sample data** to fill the dashboard with 45 days of sample shoppers, orders, and abandoned carts. It's clearly marked: a yellow banner appears, order numbers start with SAMPLE-, and shoppers are guests. It never changes real stock, and **Remove sample data** deletes all of it in one click. Real activity is always kept separately.

---

## Where the code lives

| Improvement | Backend | Front end |
|---|---|---|
| Cart and checkout | `backend/shop.py` (tables `carts`, `cart_items`, `orders`, `order_items`) | `src/cart.tsx`, `components/CartDrawer.tsx`, `pages/Cart.tsx`, `pages/Checkout.tsx`, `pages/OrderConfirmation.tsx` |
| Compare | `backend/db.py` (material, features, sleeve fields) | `src/compare.tsx`, `components/CompareToggle.tsx`, `components/CompareTray.tsx`, `pages/Compare.tsx` |
| Breadcrumbs | — | `components/Breadcrumbs.tsx` |
| Fast loading | `backend/images.py`, `backend/db.py` (cache), `backend/main.py` (gzip, ETag, image caching) | `src/api.ts` (shared catalogue), lazy-loaded pages in `src/App.tsx` |
| Form validation | `backend/validation.py` (used by `auth.py` and `shop.py`) | `src/useFormValidation.ts`, `components/Field.tsx` |
| Analytics dashboard | `backend/analytics.py` (table `analytics_events`, `users.is_admin`) | `pages/AdminDashboard.tsx` |

The new database tables and their fields are listed in section 9 of `output/harness.md`.
