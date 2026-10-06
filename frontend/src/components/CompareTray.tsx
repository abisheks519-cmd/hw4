import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { getProducts, type Product } from "../api";
import { MAX_COMPARE, useCompare } from "../compare";

const HIDDEN_ON = ["/compare", "/checkout", "/admin"];

// A bar along the bottom of the page showing the products picked for comparison.
export default function CompareTray() {
  const compare = useCompare();
  const { pathname } = useLocation();
  const [products, setProducts] = useState<Product[]>([]);

  useEffect(() => {
    if (compare.ids.length) getProducts().then(setProducts).catch(() => undefined);
  }, [compare.ids.length]);

  if (!compare.ids.length || HIDDEN_ON.includes(pathname) || pathname.startsWith("/order/")) return null;
  const picked = compare.ids.map((id) => products.find((p) => p.product_id === id)).filter((p): p is Product => Boolean(p));
  const ready = compare.ids.length >= 2;

  return (
    <div className="compare-tray" role="region" aria-label="Compare products">
      <div className="compare-tray-items">
        {Array.from({ length: MAX_COMPARE }, (_, i) => {
          const p = picked[i];
          return p ? (
            <div key={p.product_id} className="compare-slot filled" title={p.name}>
              <img src={p.thumb_url} alt={p.name} />
              <button aria-label={`Remove ${p.name}`} onClick={() => compare.remove(p.product_id)}>
                ×
              </button>
            </div>
          ) : (
            <div key={i} className="compare-slot" aria-hidden="true" />
          );
        })}
      </div>
      <div className="compare-tray-text">
        <strong>
          {compare.ids.length} of {MAX_COMPARE} picked
        </strong>
        <span>{ready ? "Ready to compare side by side" : "Pick one more item to compare"}</span>
      </div>
      <Link to="/compare" className={`btn btn-primary compare-tray-go ${ready ? "" : "disabled"}`} aria-disabled={!ready} onClick={(e) => !ready && e.preventDefault()}>
        Compare
      </Link>
      <button className="compare-tray-clear" onClick={compare.clear}>
        Clear
      </button>
    </div>
  );
}
