import { formatPrice, type Cart } from "../api";

// Subtotal, shipping, tax, and total, as priced by the server.
type Totals = Pick<Cart, "subtotal" | "shipping" | "tax" | "total"> & { item_count?: number; tax_rate?: number };

export default function OrderSummary({ cart, children }: { cart: Totals; children?: React.ReactNode }) {
  return (
    <div className="summary-lines">
      <div>
        <span>Subtotal{cart.item_count !== undefined && ` (${cart.item_count} item${cart.item_count === 1 ? "" : "s"})`}</span>
        <span>{formatPrice(cart.subtotal)}</span>
      </div>
      <div>
        <span>Shipping</span>
        <span>{cart.shipping === 0 ? <em className="free">Free</em> : formatPrice(cart.shipping)}</span>
      </div>
      <div>
        <span>Tax{cart.tax_rate !== undefined && ` (CT ${(cart.tax_rate * 100).toFixed(2)}%)`}</span>
        <span>{formatPrice(cart.tax)}</span>
      </div>
      <div className="summary-total">
        <span>Total</span>
        <span>{formatPrice(cart.total)}</span>
      </div>
      {children}
    </div>
  );
}
