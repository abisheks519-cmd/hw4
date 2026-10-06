import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import ProductCard from "../components/ProductCard";
import CompareToggle from "../components/CompareToggle";
import QuantityStepper from "../components/QuantityStepper";
import { formatPrice, getProduct, getProducts, peekProduct, track, type Product } from "../api";
import { useAssistantResults } from "../assistantResults";
import { useCart } from "../cart";
import { openChat } from "../chatHistory";
import { swatch } from "../swatches";

function stockLabel(qty: number) {
  if (qty === 0) return { text: "Out of stock", tone: "out" };
  if (qty <= 5) return { text: `Only ${qty} left`, tone: "low" };
  return { text: `${qty} in stock`, tone: "ok" };
}

// The big product photo. Hovering zooms in where the pointer is, to show detail.
function DetailStage({ product }: { product: Product }) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (e: React.PointerEvent) => {
    const el = ref.current;
    if (!el || e.pointerType !== "mouse") return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--zx", `${((e.clientX - r.left) / r.width) * 100}%`);
    el.style.setProperty("--zy", `${((e.clientY - r.top) / r.height) * 100}%`);
  };
  const cut = Boolean(product.cutout_url);
  return (
    <div className="detail-stage-wrap">
      <div
        ref={ref}
        className={`detail-stage ${cut ? "" : "photo"}`}
        onPointerMove={move}
        onPointerEnter={(e) => e.pointerType === "mouse" && ref.current?.classList.add("zooming")}
        onPointerLeave={() => ref.current?.classList.remove("zooming")}
      >
        <img src={product.cutout_url ?? product.image_url} alt={product.name} />
      </div>
      <p className="detail-stage-hint">Hover to zoom</p>
    </div>
  );
}

export default function ProductDetail() {
  const { productId = "" } = useParams();
  const [product, setProduct] = useState<Product | null>(null);
  const [related, setRelated] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [size, setSize] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);
  const [cartError, setCartError] = useState<string | null>(null);
  const [needSize, setNeedSize] = useState(false);
  const { results } = useAssistantResults();
  const { add } = useCart();
  // The page the shopper opened this product from (the results show on every page but this one).
  const backTo = (useLocation().state as { from?: string } | null)?.from ?? "/products";
  // Show the copy already downloaded with the catalogue straight away (so the page appears
  // instantly), then swap in the fresh copy from the server.
  const shown = product?.product_id === productId ? product : peekProduct(productId);

  useEffect(() => {
    setError(null);
    setSize(null);
    setQuantity(1);
    setCartError(null);
    setNeedSize(false);
    getProduct(productId)
      .then((p) => {
        setProduct(p);
        track({ type: "product_view", product_id: p.product_id });
        return getProducts().then((all) =>
          setRelated(all.filter((o) => o.category === p.category && o.product_id !== p.product_id).slice(0, 4)),
        );
      })
      .catch((e: Error) => setError(e.message === "Not found" ? "We couldn't find that product." : "We couldn't load this product."));
  }, [productId]);

  if (error)
    return (
      <div className="container page center">
        <h1>{error}</h1>
        <Link to="/products" className="btn btn-primary">
          Back to Products
        </Link>
      </div>
    );
  if (!shown) return <div className="container page"><div className="detail skeleton-detail" /></div>;

  const p = shown;
  const selected = p.inventory.find((i) => i.size === size);
  const overall = stockLabel(p.total_stock);

  const addToCart = async () => {
    if (!selected) {
      setNeedSize(true);
      return;
    }
    setAdding(true);
    setCartError(null);
    try {
      await add(p.product_id, selected.size, quantity);
      setQuantity(1);
    } catch (e) {
      setCartError(e instanceof Error ? e.message : "Couldn't add to cart.");
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="detail-page">
      <div className="container page">
        {results && (
          <Link to={backTo} state={{ keepResults: true }} className="back-to-results">
            ← Back to your {results.source === "search" ? "search" : "assistant"} results: {results.title}
          </Link>
        )}
        <div className="detail">
          <DetailStage product={p} />

          <div className="detail-info">
            <span className="eyebrow">{p.garment_type}</span>
            <h1>{p.name}</h1>
            <div className="detail-price-row">
              <span className="detail-price">{formatPrice(p.price)}</span>
              <span className={`stock-pill ${overall.tone}`}>{overall.text}</span>
            </div>

            <p className="detail-description">{p.description}</p>

            <div className="detail-block">
              <h4>Colors</h4>
              <div className="color-list">
                {p.colors.map((c) => (
                  <span key={c} className="color-chip">
                    <i style={{ background: swatch(c) }} />
                    {c}
                  </span>
                ))}
              </div>
            </div>

            <div className="detail-block">
              <h4>
                Size {selected && <span className={`stock-note ${stockLabel(selected.quantity).tone}`}>— {stockLabel(selected.quantity).text}</span>}
                {p.inventory.some((i) => i.quantity > 0 && i.quantity <= 5) && <span className="size-legend">5 or fewer left</span>}
              </h4>
              <div className="size-grid">
                {p.inventory.map((i) => (
                  <button
                    key={i.size}
                    className={`size-btn ${size === i.size ? "selected" : ""} ${i.quantity === 0 ? "sold-out" : ""} ${i.quantity > 0 && i.quantity <= 5 ? "low" : ""}`}
                    disabled={i.quantity === 0}
                    title={stockLabel(i.quantity).text}
                    onClick={() => {
                      setSize(i.size);
                      setNeedSize(false);
                      setQuantity(1);
                    }}
                  >
                    {i.size}
                  </button>
                ))}
              </div>
              {needSize && !selected && <p className="field-error">Please choose a size first.</p>}
            </div>

            <div className="buy-box">
              {p.total_stock === 0 ? (
                <button className="btn btn-primary full" disabled>Sold out</button>
              ) : (
                <>
                  <QuantityStepper value={quantity} max={selected?.quantity ?? 1} disabled={!selected || adding} onChange={setQuantity} />
                  <button className="btn btn-primary buy-btn" onClick={addToCart} disabled={adding}>
                    {adding ? "Adding…" : selected ? `Add to cart · ${formatPrice(p.price * quantity)}` : "Select a size"}
                  </button>
                </>
              )}
              <CompareToggle productId={p.product_id} variant="detail" />
            </div>
            {cartError && <div className="form-notice error">{cartError}</div>}

            <ul className="trust-row">
              <li><span>🚚</span>Free shipping over $75</li>
              <li><span>🔒</span>Secure checkout</li>
              <li>
                <button onClick={openChat}><span>💬</span>Questions? Ask our assistant</button>
              </li>
            </ul>

            <details className="detail-more">
              <summary>Stock by size</summary>
              <table className="stock-table">
                <tbody>
                  {p.inventory.map((i) => {
                    const s = stockLabel(i.quantity);
                    return (
                      <tr key={i.size}>
                        <td>{i.size}</td>
                        <td>
                          <span className={`stock-pill ${s.tone}`}>{s.text}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </details>
            {(p.material || p.features.length > 0) && (
              <details className="detail-more">
                <summary>Details</summary>
                <ul className="detail-specs">
                  {p.material && <li><strong>Material</strong>{p.material}</li>}
                  {p.sleeve && <li><strong>Sleeve</strong>{p.sleeve}</li>}
                  {p.features.length > 0 && <li><strong>Features</strong>{p.features.join(" · ")}</li>}
                </ul>
              </details>
            )}
            <details className="detail-more">
              <summary>Tags</summary>
              <div className="tag-list">
                {p.search_tags.map((t) => (
                  <span key={t} className="tag">
                    {t}
                  </span>
                ))}
              </div>
            </details>
          </div>
        </div>

        {related.length > 0 && (
          <section className="section related">
            <div className="section-head" data-reveal>
              <h2>You might also like</h2>
              <Link to={`/products?category=${encodeURIComponent(p.category)}`} className="link-arrow">
                All {p.category} ›
              </Link>
            </div>
            <div className="product-grid">
              {related.map((r, i) => (
                <div key={r.product_id} data-reveal style={{ ["--d" as string]: `${i * 70}ms` }}>
                  <ProductCard product={r} />
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
