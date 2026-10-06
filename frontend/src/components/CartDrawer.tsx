import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { formatPrice } from "../api";
import { useCart } from "../cart";
import QuantityStepper from "./QuantityStepper";

// Slides in from the right after something is added, or from the cart button in the header.
export default function CartDrawer() {
  const { cart, drawerOpen, closeDrawer, lastAdded, setQuantity, remove } = useCart();
  const { pathname } = useLocation();
  const [busy, setBusy] = useState(false);

  useEffect(closeDrawer, [pathname]); // close when the shopper goes to another page
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeDrawer();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  if (!drawerOpen) return null;
  const items = cart?.items ?? [];
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    await fn().catch(() => undefined);
    setBusy(false);
  };
  const progress = cart ? Math.min(100, (cart.subtotal / cart.free_shipping_at) * 100) : 0;

  return (
    <div className="drawer-layer">
      <div className="drawer-backdrop" onClick={closeDrawer} />
      <aside className="drawer" role="dialog" aria-label="Your cart">
        <div className="drawer-head">
          <h3>Your cart {cart && cart.item_count > 0 && <span>({cart.item_count})</span>}</h3>
          <button className="drawer-close" aria-label="Close cart" onClick={closeDrawer}>
            ×
          </button>
        </div>

        {lastAdded && items.some((i) => i.product_id === lastAdded.productId && i.size === lastAdded.size) && (
          <div className="drawer-added">✓ Added to your cart</div>
        )}

        {items.length === 0 ? (
          <div className="drawer-empty">
            <div className="drawer-empty-icon">🛍️</div>
            <p>Your cart is empty</p>
            <Link to="/products" className="btn btn-primary" onClick={closeDrawer}>
              Browse products
            </Link>
          </div>
        ) : (
          <>
            <ul className="drawer-items">
              {items.map((i) => (
                <li key={`${i.product_id}-${i.size}`} className={lastAdded?.productId === i.product_id && lastAdded.size === i.size ? "just-added" : ""}>
                  <Link to={`/products/${i.product_id}`} onClick={closeDrawer}>
                    <img src={i.thumb_url} alt="" />
                  </Link>
                  <div className="drawer-item-info">
                    <Link to={`/products/${i.product_id}`} onClick={closeDrawer}>
                      <strong>{i.name}</strong>
                    </Link>
                    <span>
                      Size {i.size} · {formatPrice(i.unit_price)}
                    </span>
                    {i.warning && <span className="line-warning">{i.warning}</span>}
                    <div className="drawer-item-row">
                      <QuantityStepper value={i.quantity} max={i.available} disabled={busy || i.available === 0} onChange={(q) => run(() => setQuantity(i.product_id, i.size, q))} />
                      <button className="link-btn" disabled={busy} onClick={() => run(() => remove(i.product_id, i.size))}>
                        Remove
                      </button>
                    </div>
                  </div>
                  <strong className="drawer-item-total">{formatPrice(i.line_total)}</strong>
                </li>
              ))}
            </ul>
            <div className="drawer-foot">
              <div className="ship-progress">
                <span>
                  {cart!.free_shipping_remaining > 0
                    ? <>Add <strong>{formatPrice(cart!.free_shipping_remaining)}</strong> for free shipping</>
                    : <>🎉 You've unlocked <strong>free shipping</strong></>}
                </span>
                <div className="ship-bar"><i style={{ width: `${progress}%` }} /></div>
              </div>
              <div className="drawer-subtotal">
                <span>Subtotal</span>
                <strong>{formatPrice(cart!.subtotal)}</strong>
              </div>
              <p className="drawer-note">Shipping and tax are shown at checkout.</p>
              <Link to="/checkout" className="btn btn-primary full" onClick={closeDrawer}>
                Proceed to checkout
              </Link>
              <Link to="/cart" className="btn btn-outline full" onClick={closeDrawer}>
                View cart
              </Link>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
