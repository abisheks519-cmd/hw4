import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ProductCard from "../components/ProductCard";
import { useProducts } from "../useProducts";

type Sort = "name" | "price-asc" | "price-desc";

export default function Products() {
  const { products, loading, error } = useProducts();
  const [params, setParams] = useSearchParams();
  const category = params.get("category") ?? "All";
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("name");

  const categories = useMemo(() => ["All", ...new Set(products.map((p) => p.category))].sort((a, b) =>
    a === "All" ? -1 : b === "All" ? 1 : a.localeCompare(b)), [products]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = products.filter(
      (p) =>
        (category === "All" || p.category === category) &&
        (!q || [p.name, p.description, ...p.colors, ...p.search_tags].join(" ").toLowerCase().includes(q)),
    );
    const compare = {
      name: (a: typeof list[0], b: typeof list[0]) => a.name.localeCompare(b.name),
      "price-asc": (a: typeof list[0], b: typeof list[0]) => a.price - b.price,
      "price-desc": (a: typeof list[0], b: typeof list[0]) => b.price - a.price,
    }[sort];
    return [...list].sort(compare);
  }, [products, category, query, sort]);

  const selectCategory = (c: string) => setParams(c === "All" ? {} : { category: c });
  const count = (c: string) => (c === "All" ? products.length : products.filter((p) => p.category === c).length);

  return (
    <div className="products-page">
      <header className="shop-hero">
        <div className="container">
          <span className="eyebrow">The collection</span>
          <h1 className="display">{category === "All" ? <>Shop it <em>all.</em></> : <>{category}<em>.</em></>}</h1>
          <p>Hoodies, crewnecks, tees, and more, all built for campus life.</p>
        </div>
      </header>

      {/* Sticks under the header while scrolling, so filters are always one tap away. */}
      <div className="filters">
        <div className="container filters-inner">
          <div className="chips" role="tablist" aria-label="Categories">
            {categories.map((c) => (
              <button key={c} role="tab" aria-selected={c === category} className={`chip ${c === category ? "active" : ""}`} onClick={() => selectCategory(c)}>
                {c} <span>{count(c)}</span>
              </button>
            ))}
          </div>
          <div className="filter-controls">
            <input
              type="search"
              placeholder="Filter by name, color, sport…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              <option value="name">Sort: A–Z</option>
              <option value="price-asc">Price: Low to High</option>
              <option value="price-desc">Price: High to Low</option>
            </select>
          </div>
        </div>
      </div>

      <div className="container page products-body">
        {error && <div className="alert">{error}</div>}
        {loading ? (
          <div className="product-grid">
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} className="product-card skeleton" />
            ))}
          </div>
        ) : (
          <>
            <p className="result-count">{visible.length} products</p>
            <div className="product-grid">
              {visible.map((p, i) => (
                // Cards rise in as they scroll into view, a few at a time.
                <div key={p.product_id} data-reveal style={{ ["--d" as string]: `${(i % 4) * 60}ms` }}>
                  <ProductCard product={p} />
                </div>
              ))}
            </div>
            {!visible.length && !error && <p className="muted center">No products match your search.</p>}
          </>
        )}
      </div>
    </div>
  );
}
