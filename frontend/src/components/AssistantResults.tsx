import { useEffect, useRef } from "react";
import { useMatch } from "react-router-dom";
import ProductCard from "./ProductCard";
import { useAssistantResults } from "../assistantResults";

// The products the chat assistant found, shown as a grid at the top of the page.
// Hidden on a product page (that page links back here instead).
export default function AssistantResults() {
  const { results, clearResults } = useAssistantResults();
  const onProductPage = useMatch("/products/:productId");
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (results && !onProductPage) sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    // Scroll only when a new set of results arrives, not on every render.
  }, [results?.id]);

  if (!results || onProductPage) return null;
  const count = results.products.length;
  const fromSearch = results.source === "search";
  const summary =
    results.total && results.total > count
      ? `Showing ${count} of ${results.total} items · try a more specific search to narrow it down`
      : `${count} item${count === 1 ? "" : "s"} · click any item for the full details`;

  return (
    <section ref={sectionRef} key={results.id} className="assistant-results" aria-live="polite">
      <div className="container">
        <div className="assistant-results-head">
          <div>
            <span className="eyebrow">
              {fromSearch ? `🔍 Search results for \u201c${results.query}\u201d` : "✨ Picked by your shopping assistant"}
            </span>
            <h2>{count > 0 ? results.title : `No results for \u201c${results.query ?? results.title}\u201d`}</h2>
            <p className="muted">
              {results.error ??
                (count > 0 ? summary : "Try a garment type (hoodie, T-shirt, crewneck), a color, a team, or a price like \u201cunder $50\u201d.")}
            </p>
          </div>
          <button className="btn btn-outline assistant-results-clear" onClick={clearResults}>
            Clear results
          </button>
        </div>
        <div className="product-grid">
          {results.products.map((p, i) => (
            <div key={p.product_id} className="result-item" style={{ animationDelay: `${Math.min(i, 12) * 40}ms` }}>
              <ProductCard product={p} />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
