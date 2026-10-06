import { useState } from "react";
import { Link } from "react-router-dom";
import { formatPrice } from "../api";
import { useAuth } from "../auth";
import { useCart } from "../cart";
import OrderSummary from "../components/OrderSummary";
import QuantityStepper from "../components/QuantityStepper";

export default function CartPage() {
  const { cart, setQuantity, remove, clear } = useCart();
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    await fn().catch((e: Error) => setError(e.message));
    setBusy(false);
  };

  if (!cart) return <div className="container page"><div className="skeleton-detail" /></div>;
  const items = cart.items;

  return (
    <div className="container page">
      <div className="page-head">
        <h1>Your cart</h1>
        <p className="muted">
          {user
            ? "Your cart is saved to your account, so it'll be here when you come back."
            : <>Shopping as a guest. <Link to="/login" className="inline-link">Log in</Link> to save your cart to your account.</>}
        </p>
      </div>

      {items.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🛍️</div>
          <h2>Your cart is empty</h2>
          <p className="muted">Find something you love and add it here.</p>
          <Link to="/products" className="btn btn-primary">
            Browse products
          </Link>
        </div>
      ) : (
        <div className="cart-layout">
          <div className="cart-lines">
            {error && <div className="alert">{error}</div>}
            {items.map((i) => (
              <div key={`${i.product_id}-${i.size}`} className="cart-line">
                <Link to={`/products/${i.product_id}`} className="cart-line-img">
                  <img src={i.thumb_url} alt={i.name} />
                </Link>
                <div className="cart-line-info">
                  <span className="eyebrow">{i.category}</span>
                  <Link to={`/products/${i.product_id}`}>
                    <h3>{i.name}</h3>
                  </Link>
                  <span className="muted">
                    Size {i.size} · {formatPrice(i.unit_price)} each · {i.available > 0 ? `${i.available} in stock` : "sold out"}
                  </span>
                  {i.warning && <span className="line-warning">{i.warning}</span>}
                  <div className="cart-line-actions">
                    <QuantityStepper value={i.quantity} max={i.available} disabled={busy || i.available === 0} onChange={(q) => run(() => setQuantity(i.product_id, i.size, q))} />
                    <button className="link-btn" disabled={busy} onClick={() => run(() => remove(i.product_id, i.size))}>
                      Remove
                    </button>
                  </div>
                </div>
                <strong className="cart-line-total">{formatPrice(i.line_total)}</strong>
              </div>
            ))}
            <div className="cart-lines-foot">
              <Link to="/products" className="inline-link">
                ← Continue shopping
              </Link>
              <button className="link-btn" disabled={busy} onClick={() => run(clear)}>
                Empty cart
              </button>
            </div>
          </div>

          <aside className="summary-card">
            <h3>Order summary</h3>
            <div className="ship-progress">
              <span>
                {cart.free_shipping_remaining > 0
                  ? <>Add <strong>{formatPrice(cart.free_shipping_remaining)}</strong> more for free shipping</>
                  : <>🎉 Your order ships <strong>free</strong></>}
              </span>
              <div className="ship-bar"><i style={{ width: `${Math.min(100, (cart.subtotal / cart.free_shipping_at) * 100)}%` }} /></div>
            </div>
            <OrderSummary cart={cart} />
            <Link to="/checkout" className="btn btn-primary full">
              Proceed to checkout · {formatPrice(cart.total)}
            </Link>
            <p className="summary-note">🔒 Secure checkout · Free shipping on orders over {formatPrice(cart.free_shipping_at)}</p>
          </aside>
        </div>
      )}
    </div>
  );
}
