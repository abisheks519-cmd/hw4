import { useEffect, useState } from "react";
import { Link, matchPath, useLocation } from "react-router-dom";
import { getProducts, type Product } from "../api";
import { useCompare } from "../compare";

interface Crumb {
  label: string;
  to?: string;
}

const HOME: Crumb = { label: "Home", to: "/" };
const PRODUCTS: Crumb = { label: "Products", to: "/products" };
const CART: Crumb = { label: "Cart", to: "/cart" };
const SIMPLE: Record<string, string> = {
  "/about": "About Us",
  "/login": "Log in",
  "/create-account": "Create account",
  "/logout": "Logged out",
  "/admin": "Admin dashboard",
};

// Shows where the shopper is, e.g. Home › Products › Hoodies › Basic Hoodie Big Yale.
// Every step but the last is a link back up.
export default function Breadcrumbs() {
  const { pathname, search } = useLocation();
  const compare = useCompare();
  const [products, setProducts] = useState<Product[]>([]);
  const productMatch = matchPath("/products/:productId", pathname);

  useEffect(() => {
    if (productMatch) getProducts().then(setProducts).catch(() => undefined);
  }, [productMatch?.params.productId]);

  let crumbs: Crumb[] = [];
  if (pathname === "/products") {
    const category = new URLSearchParams(search).get("category");
    crumbs = category ? [HOME, PRODUCTS, { label: category }] : [HOME, { label: "Products" }];
  } else if (productMatch) {
    const product = products.find((p) => p.product_id === productMatch.params.productId);
    crumbs = [HOME, PRODUCTS];
    if (product) crumbs.push({ label: product.category, to: `/products?category=${encodeURIComponent(product.category)}` }, { label: product.name });
    else crumbs.push({ label: "…" });
  } else if (pathname === "/cart") {
    crumbs = [HOME, { label: "Cart" }];
  } else if (pathname === "/checkout") {
    crumbs = [HOME, CART, { label: "Checkout" }];
  } else if (matchPath("/order/:orderNumber", pathname)) {
    crumbs = [HOME, CART, { label: "Checkout" }, { label: "Order confirmed" }];
  } else if (pathname === "/compare") {
    crumbs = [HOME, PRODUCTS, { label: `Compare (${compare.ids.length})` }];
  } else if (SIMPLE[pathname]) {
    crumbs = [HOME, { label: SIMPLE[pathname] }];
  } else if (pathname !== "/") {
    crumbs = [HOME, { label: "Page not found" }];
  }
  if (!crumbs.length) return null;

  return (
    <nav className="crumbs" aria-label="Breadcrumb">
      <ol className="container">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <li key={i}>
              {c.to && !last ? <Link to={c.to}>{i === 0 ? <><HomeIcon /> {c.label}</> : c.label}</Link> : <span aria-current={last ? "page" : undefined}>{c.label}</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="crumbs-home">
      <path d="M3 11 12 4l9 7M5 10v10h5v-6h4v6h5V10" />
    </svg>
  );
}
