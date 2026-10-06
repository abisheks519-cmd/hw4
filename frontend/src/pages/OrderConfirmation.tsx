import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { formatPrice, getOrder, type Order } from "../api";
import OrderSummary from "../components/OrderSummary";

export default function OrderConfirmation() {
  const { orderNumber = "" } = useParams();
  const passed = (useLocation().state as { order?: Order } | null)?.order;
  const [order, setOrder] = useState<Order | null>(passed?.order_number === orderNumber ? passed : null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!order) getOrder(orderNumber).then(setOrder).catch(() => setError("We couldn't find that order."));
  }, [orderNumber]);

  if (error)
    return (
      <div className="container page center">
        <h1>{error}</h1>
        <Link to="/products" className="btn btn-primary">Back to Products</Link>
      </div>
    );
  if (!order) return <div className="container page"><div className="skeleton-detail" /></div>;

  return (
    <div className="container page">
      <div className="order-card">
        <div className="logout-check">
          <svg viewBox="0 0 52 52" aria-hidden="true">
            <circle className="logout-check-circle" cx="26" cy="26" r="24" fill="none" />
            <path className="logout-check-mark" fill="none" d="M15 27l7 7 15-15" />
          </svg>
        </div>
        <span className="eyebrow">Order confirmed</span>
        <h1>Thank you, {order.full_name.split(" ")[0]}!</h1>
        <p className="muted">
          Your order <strong className="order-number">{order.order_number}</strong> has been placed. Keep this number for your records.
        </p>

        <div className="order-grid">
          <div>
            <h4>Shipping to</h4>
            <p>{order.full_name}<br />{order.ship_to}</p>
          </div>
          <div>
            <h4>Contact</h4>
            <p>{order.email}<br />{order.phone}</p>
          </div>
          <div>
            <h4>Paid with</h4>
            <p>{order.card}</p>
          </div>
        </div>

        <ul className="summary-items">
          {order.items.map((i) => (
            <li key={`${i.product_id}-${i.size}`}>
              <div className="summary-thumb">
                {i.thumb_url && <img src={i.thumb_url} alt="" />}
                <span>{i.quantity}</span>
              </div>
              <div>
                <Link to={`/products/${i.product_id}`}><strong>{i.name}</strong></Link>
                <span>Size {i.size} · {formatPrice(i.unit_price)} each</span>
              </div>
              <span>{formatPrice(i.line_total)}</span>
            </li>
          ))}
        </ul>
        <OrderSummary cart={order} />
        <div className="logout-actions">
          <Link to="/products" className="btn btn-primary">Continue shopping</Link>
          <Link to="/" className="btn btn-outline">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
