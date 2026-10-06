import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { formatPrice, getProducts, track, type Product } from "../api";
import { MAX_COMPARE, useCompare } from "../compare";

const SIZES = ["XS", "S", "M", "L", "XL", "XXL"];

interface Row {
  label: string;
  key: (p: Product) => string; // what counts as "the same" for Highlight differences
  render: (p: Product, all: Product[]) => ReactNode;
}

const ROWS: Row[] = [
  {
    label: "Price",
    key: (p) => String(p.price),
    render: (p, all) => {
      const low = Math.min(...all.map((x) => x.price));
      return (
        <>
          <span className="compare-price">{formatPrice(p.price)}</span>
          {all.length > 1 && p.price === low && all.some((x) => x.price !== low) && <span className="compare-badge best">Lowest price</span>}
        </>
      );
    },
  },
  { label: "Type of clothing", key: (p) => p.garment_type.toLowerCase(), render: (p) => <span className="capitalize">{p.garment_type}</span> },
  { label: "Category", key: (p) => p.category, render: (p) => p.category },
  {
    label: "Colors",
    key: (p) => [...p.colors].sort().join(","),
    render: (p) => (
      <div className="tag-list">
        {p.colors.map((c) => (
          <span key={c} className="tag tag-color">{c}</span>
        ))}
      </div>
    ),
  },
  {
    label: "Material",
    key: (p) => p.material ?? "",
    render: (p) => (p.material ? p.material : <span className="muted">Not listed in the catalogue</span>),
  },
  { label: "Sleeve", key: (p) => p.sleeve ?? "", render: (p) => p.sleeve ?? "—" },
  {
    label: "Features",
    key: (p) => p.features.join(","),
    render: (p) =>
      p.features.length ? (
        <ul className="compare-features">
          {p.features.map((f) => (
            <li key={f}>✓ {f}</li>
          ))}
        </ul>
      ) : (
        <span className="muted">—</span>
      ),
  },
  {
    label: "Sizes in stock",
    key: (p) => p.inventory.filter((i) => i.quantity > 0).map((i) => i.size).join(","),
    render: (p) => (
      <div className="compare-sizes">
        {SIZES.map((s) => {
          const inv = p.inventory.find((i) => i.size === s);
          const qty = inv?.quantity ?? 0;
          return (
            <span key={s} className={qty > 0 ? (qty <= 5 ? "low" : "ok") : "out"} title={inv ? `${qty} in stock` : "Not offered"}>
              {s}
            </span>
          );
        })}
      </div>
    ),
  },
  {
    label: "Total in stock",
    key: (p) => String(p.total_stock),
    render: (p, all) => (
      <>
        {p.total_stock > 0 ? `${p.total_stock} available` : <span className="stock-pill out">Sold out</span>}
        {all.length > 1 && p.total_stock === Math.max(...all.map((x) => x.total_stock)) && p.total_stock > 0 && all.some((x) => x.total_stock !== p.total_stock) && (
          <span className="compare-badge">Most in stock</span>
        )}
      </>
    ),
  },
  { label: "Description", key: (p) => p.description, render: (p) => <p className="compare-desc">{p.description}</p> },
];

export default function Compare() {
  const compare = useCompare();
  const [products, setProducts] = useState<Product[] | null>(null);
  const [differencesOnly, setDifferencesOnly] = useState(false);
  const [highlight, setHighlight] = useState(true);

  useEffect(() => {
    getProducts().then(setProducts).catch(() => setProducts([]));
  }, []);

  const picked = useMemo(
    () => compare.ids.map((id) => products?.find((p) => p.product_id === id)).filter((p): p is Product => Boolean(p)),
    [compare.ids, products],
  );

  // Record which products were compared (once per set) for the admin dashboard.
  const signature = picked.map((p) => p.product_id).join(",");
  useEffect(() => {
    if (picked.length >= 2) track({ type: "compare", product_ids: picked.map((p) => p.product_id) });
  }, [signature]);

  if (!products) return <div className="container page"><div className="skeleton-detail" /></div>;

  if (picked.length < 2)
    return (
      <div className="container page">
        <div className="empty-state">
          <div className="empty-state-icon">⚖️</div>
          <h2>Compare products side by side</h2>
          <p className="muted">
            {picked.length === 1 ? "You've picked 1 item. Pick at least one more" : "Pick 2 to 4 items"} using the <strong>Compare</strong> box on any product card or product page.
          </p>
          <Link to="/products" className="btn btn-primary">Browse products</Link>
        </div>
      </div>
    );

  const rows = ROWS.map((r) => ({ ...r, differs: new Set(picked.map(r.key)).size > 1 }));
  const shown = differencesOnly ? rows.filter((r) => r.differs) : rows;

  return (
    <div className="container page">
      <div className="page-head compare-head">
        <div>
          <h1>Compare products</h1>
          <p className="muted">
            Comparing {picked.length} items by price, type of clothing, color, material, sizes, and more. {rows.filter((r) => r.differs).length} of {rows.length} details differ.
          </p>
        </div>
        <div className="compare-options">
          <label className="switch">
            <input type="checkbox" checked={highlight} onChange={(e) => setHighlight(e.target.checked)} />
            <span /> Highlight differences
          </label>
          <label className="switch">
            <input type="checkbox" checked={differencesOnly} onChange={(e) => setDifferencesOnly(e.target.checked)} />
            <span /> Only show differences
          </label>
          <button className="btn btn-outline small" onClick={compare.clear}>Clear all</button>
        </div>
      </div>

      <div className="compare-scroll">
        <table className="compare-table" style={{ ["--cols" as string]: picked.length }}>
          <thead>
            <tr>
              <th className="compare-label" />
              {picked.map((p) => (
                <th key={p.product_id}>
                  <div className="compare-product">
                    <button className="compare-remove" aria-label={`Remove ${p.name}`} onClick={() => compare.remove(p.product_id)}>×</button>
                    <Link to={`/products/${p.product_id}`}>
                      <img src={p.thumb_url} alt={p.name} />
                      <strong>{p.name}</strong>
                    </Link>
                    <Link to={`/products/${p.product_id}`} className="btn btn-primary small">View &amp; add to cart</Link>
                  </div>
                </th>
              ))}
              {picked.length < MAX_COMPARE && (
                <th className="compare-add">
                  <Link to="/products">
                    <span>＋</span>Add another item
                  </Link>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.label} className={highlight && r.differs ? "differs" : ""}>
                <th scope="row" className="compare-label">
                  {r.label}
                  {highlight && r.differs && <span className="differs-dot" title="These differ" />}
                </th>
                {picked.map((p) => (
                  <td key={p.product_id}>{r.render(p, picked)}</td>
                ))}
                {picked.length < MAX_COMPARE && <td className="compare-add" />}
              </tr>
            ))}
            {shown.length === 0 && (
              <tr>
                <td colSpan={picked.length + 2} className="center muted">These items match on every detail.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
