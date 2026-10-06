export interface SizeStock {
  size: string;
  quantity: number;
}

export interface Product {
  product_id: string;
  name: string;
  garment_type: string;
  category: string;
  description: string;
  short_description: string;
  colors: string[];
  search_tags: string[];
  image_url: string; // compressed WebP, product-page size
  thumb_url: string; // smaller WebP for cards and thumbnails
  original_image_url: string;
  cutout_url: string | null; // product with its photo background removed (null: use the photo)
  cutout_thumb_url: string | null;
  price: number;
  inventory: SizeStock[];
  total_stock: number;
  material: string | null; // fabric named in the catalogue, if any
  features: string[];
  sleeve: string | null;
}

// POST /api/chat response. When `results_title` is set, `products` is a set of matches
// the website shows as a results grid on the page (see AssistantResults).
export interface ChatReply {
  reply: string;
  results_title: string | null;
  products: Product[];
  // Signed-in shoppers: the saved conversation this exchange was stored in.
  conversation_id: number | null;
  conversation_title: string | null;
}

// What the shopper is looking at, sent with each chat message so the assistant knows what
// "this one" means. Only ids and the page type; the server looks up the details.
export interface PageContext {
  path: string;
  page:
    | "home" | "products" | "product" | "about" | "login" | "create-account" | "logout"
    | "cart" | "checkout" | "order" | "compare" | "admin" | "other";
  product_id: string | null;
  category: string | null;
  results: { title: string; product_ids: string[] } | null;
}

// Saved chat history (signed-in shoppers only).
export interface ConversationSummary {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
  results_title: string | null;
  products: Product[];
  created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: StoredMessage[];
}

// GET /api/search response (the header search bar).
export interface SearchReply {
  query: string;
  results_title: string | null;
  total_matches: number;
  products: Product[];
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface User {
  id: number;
  first_name: string | null;
  last_name: string | null;
  name: string;
  email: string;
  is_admin: boolean;
}

export interface SignupInput {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  confirm_password: string;
}

// Pulls a human-readable message out of FastAPI's error responses.
function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "");
  if (status === 404) return "Not found";
  return `Request failed (${status})`;
}

// An API error, with per-field messages when the server's form validation rejected the request.
export class ApiError extends Error {
  constructor(message: string, public status: number, public errors: Record<string, string> = {}) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(errorMessage(res.status, body), res.status, (body as { errors?: Record<string, string> })?.errors);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const postJson = <T>(path: string, data: unknown) =>
  request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

const sendJson = <T>(method: string, path: string, data?: unknown) =>
  request<T>(path, { method, headers: { "Content-Type": "application/json" }, body: data === undefined ? undefined : JSON.stringify(data) });

// The catalogue is fetched once and shared by every page (the server also answers with a 304
// "not modified" when the browser already has it). Cleared after checkout, when stock changes.
const CATALOGUE_MS = 60_000;
let catalogue: { at: number; promise: Promise<Product[]> } | null = null;
const loaded = new Map<string, Product>(); // last catalogue received, for instant product pages
export function getProducts(): Promise<Product[]> {
  if (!catalogue || Date.now() - catalogue.at > CATALOGUE_MS) {
    const promise = request<Product[]>("/api/products");
    catalogue = { at: Date.now(), promise };
    promise.then((all) => all.forEach((p) => loaded.set(p.product_id, p))).catch(() => (catalogue = null));
  }
  return catalogue.promise;
}
// A product already downloaded with the catalogue, so its page can appear without waiting.
export const peekProduct = (id: string) => loaded.get(id) ?? null;
export const getProduct = (id: string) => request<Product>(`/api/products/${encodeURIComponent(id)}`);
export const refreshCatalogue = () => (catalogue = null);
export const sendChat = (
  message: string,
  options: { history?: ChatTurn[]; conversationId?: number | null; pageContext?: PageContext } = {},
) =>
  postJson<ChatReply>("/api/chat", {
    message,
    history: options.history ?? [],
    conversation_id: options.conversationId ?? null,
    page_context: options.pageContext ?? null,
  });

export const listChats = () => request<ConversationSummary[]>("/api/chats");
export const getChat = (id: number) => request<ConversationDetail>(`/api/chats/${id}`);
export const deleteChat = (id: number) => fetch(`/api/chats/${id}`, { method: "DELETE" });

export const searchCatalogue = (q: string) => request<SearchReply>(`/api/search?q=${encodeURIComponent(q)}`);

export const signup = (input: SignupInput) => postJson<User>("/api/auth/signup", input);
export const login = (email: string, password: string) => postJson<User>("/api/auth/login", { email, password });
// The session lives in an HttpOnly cookie the browser sends automatically.
export const getMe = () => request<User | null>("/api/auth/me");
export const logout = () => fetch("/api/auth/logout", { method: "POST" });

export const formatPrice = (price: number) => `$${price.toFixed(2)}`;

// ---- Cart and checkout -------------------------------------------------------------------

export interface CartLine {
  product_id: string;
  name: string;
  category: string;
  size: string;
  quantity: number;
  unit_price: number;
  line_total: number;
  thumb_url: string;
  available: number;
  warning: string | null;
}

export interface Cart {
  items: CartLine[];
  item_count: number;
  subtotal: number;
  shipping: number;
  tax: number;
  total: number;
  free_shipping_at: number;
  free_shipping_remaining: number;
  tax_rate: number;
  saved_to_account: boolean;
}

export interface CheckoutInput {
  full_name: string;
  email: string;
  phone: string;
  address1: string;
  address2: string;
  city: string;
  state: string;
  zip: string;
  card_name: string;
  card_number: string;
  expiry: string;
  cvv: string;
}

export interface Order {
  order_number: string;
  created_at: string;
  full_name: string;
  email: string;
  phone: string;
  ship_to: string;
  card: string;
  items: { product_id: string; name: string; size: string; quantity: number; unit_price: number; line_total: number; thumb_url: string | null }[];
  item_count: number;
  subtotal: number;
  shipping: number;
  tax: number;
  total: number;
}

const item = (product_id: string, size: string, quantity = 1) => ({ product_id, size, quantity });
export const getCart = () => request<Cart>("/api/cart");
export const addToCart = (productId: string, size: string, quantity = 1) => sendJson<Cart>("POST", "/api/cart/items", item(productId, size, quantity));
export const setCartQuantity = (productId: string, size: string, quantity: number) =>
  sendJson<Cart>("PATCH", "/api/cart/items", item(productId, size, quantity));
export const removeFromCart = (productId: string, size: string) =>
  request<Cart>(`/api/cart/items?product_id=${encodeURIComponent(productId)}&size=${encodeURIComponent(size)}`, { method: "DELETE" });
export const clearCart = () => request<Cart>("/api/cart", { method: "DELETE" });
export const placeOrder = (input: CheckoutInput) => sendJson<Order>("POST", "/api/checkout", input);
export const getOrder = (orderNumber: string) => request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}`);

// ---- Form validation (the server's rules, checked as each field is filled in) ----------------

export type FormName = "signup" | "login" | "checkout";
export interface ValidationResult {
  valid: boolean;
  errors: Record<string, string>;
  cleaned: Record<string, string>;
}
export const validateFields = (form: FormName, data: Record<string, string>, fields?: string[]) =>
  sendJson<ValidationResult>("POST", `/api/validate/${form}${fields ? `?fields=${fields.join(",")}` : ""}`, data);

// ---- Analytics ---------------------------------------------------------------------------------

export type ClientEvent = { type: "product_view"; product_id: string } | { type: "checkout_started" } | { type: "compare"; product_ids: string[] };
// Fire-and-forget: tracking must never get in a shopper's way.
export const track = (event: ClientEvent) => {
  sendJson("POST", "/api/events", event).catch(() => undefined);
};

export const getAnalytics = (days: number) => request<Analytics>(`/api/admin/analytics?days=${days}`);
export const loadSampleData = () => sendJson<Record<string, number>>("POST", "/api/admin/sample-data", {});
export const clearSampleData = () => request<Record<string, number>>("/api/admin/sample-data", { method: "DELETE" });

export interface ProductBrief {
  product_id: string;
  name: string;
  category: string;
  thumb_url: string | null;
  price: number | null;
  total_stock: number | null;
}

export interface Analytics {
  range_days: number;
  generated_at: string;
  abandoned_after_minutes: number;
  includes_sample_data: boolean;
  kpis: {
    revenue: number;
    merchandise_sales: number;
    orders: number;
    units_sold: number;
    avg_order_value: number;
    units_per_order: number;
    visitors: number;
    product_views: number;
    searches: number;
    zero_result_searches: number;
    zero_result_rate: number;
    cart_adds: number;
    cart_add_units: number;
    cart_removes: number;
    checkouts_started: number;
    comparisons: number;
    conversion_rate: number;
    abandoned_carts: number;
    abandoned_value: number;
    cart_abandonment_rate: number;
  };
  daily: { date: string; revenue: number; orders: number; views: number; searches: number; cart_adds: number; visitors: number }[];
  funnel: { step: string; shoppers: number; pct_of_visitors: number; pct_of_previous: number }[];
  top_searches: SearchStat[];
  zero_result_searches: SearchStat[];
  search_sources: { search_bar: number; chat: number };
  popular_products: (ProductBrief & {
    views: number;
    cart_adds: number;
    cart_add_units: number;
    units_sold: number;
    revenue: number;
    orders: number;
    view_to_cart_pct: number;
    score: number;
  })[];
  checked_out_items: (ProductBrief & { size: string; units: number; revenue: number; orders: number })[];
  sales_by_category: { category: string; units: number; revenue: number; share_pct: number }[];
  sizes_sold: { size: string; units: number }[];
  abandoned_carts: {
    cart_id: number;
    shopper: string;
    email: string | null;
    signed_in: boolean;
    is_demo: boolean;
    last_active: string;
    idle_hours: number;
    items: (ProductBrief & { size: string; quantity: number; line_total: number })[];
    units: number;
    value: number;
  }[];
  recent_orders: {
    order_number: string;
    created_at: string;
    customer: string;
    email: string;
    signed_in: boolean;
    items: string[];
    units: number;
    total: number;
    city: string;
    is_demo: boolean;
  }[];
  low_stock: (ProductBrief & { size: string; quantity: number })[];
  low_stock_counts: { out_of_stock: number; low: number };
}

export interface SearchStat {
  query: string;
  count: number;
  avg_results: number;
  zero_results: number;
  last_searched: string;
  search_bar: number;
  chat: number;
}
