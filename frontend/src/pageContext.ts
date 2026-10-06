import { matchPath, useLocation } from "react-router-dom";
import type { PageContext } from "./api";
import { useAssistantResults } from "./assistantResults";
import { useCompare } from "./compare";

const PAGES: Record<string, PageContext["page"]> = {
  "/": "home",
  "/products": "products",
  "/about": "about",
  "/login": "login",
  "/create-account": "create-account",
  "/logout": "logout",
  "/cart": "cart",
  "/checkout": "checkout",
  "/compare": "compare",
  "/admin": "admin",
};

// What the shopper is looking at right now, sent with each chat message so the assistant can
// answer "is this in medium?" or "how much is the second one?".
export function usePageContext(): PageContext {
  const { pathname, search } = useLocation();
  const { results } = useAssistantResults();
  const compare = useCompare();
  const product = matchPath("/products/:productId", pathname);
  // On the Compare page, the products side by side are what's "on the page".
  const onCompare = pathname === "/compare" && compare.ids.length > 0;
  return {
    path: pathname + search,
    page: product ? "product" : pathname.startsWith("/order/") ? "order" : PAGES[pathname] ?? "other",
    product_id: product?.params.productId ?? null,
    category: pathname === "/products" ? new URLSearchParams(search).get("category") : null,
    // The results grid isn't shown on product pages, so only send it where the shopper can see it.
    results: onCompare
      ? { title: "Products being compared side by side", product_ids: compare.ids }
      : results && !product && results.products.length > 0
        ? { title: results.title, product_ids: results.products.slice(0, 30).map((p) => p.product_id) }
        : null,
  };
}
