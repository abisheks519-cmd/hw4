import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { formatPrice, placeOrder, refreshCatalogue, track, type CheckoutInput } from "../api";
import { useAuth } from "../auth";
import { useCart } from "../cart";
import Field from "../components/Field";
import OrderSummary from "../components/OrderSummary";
import { useFormValidation } from "../useFormValidation";

const EMPTY: CheckoutInput = {
  full_name: "", email: "", phone: "", address1: "", address2: "", city: "", state: "", zip: "",
  card_name: "", card_number: "", expiry: "", cvv: "",
};

// Light formatting as the shopper types; the server does the real checking.
const formatCard = (v: string) => v.replace(/\D/g, "").slice(0, 19).replace(/(\d{4})(?=\d)/g, "$1 ");
const formatExpiry = (v: string, prev: string) => {
  const d = v.replace(/\D/g, "").slice(0, 4);
  if (d.length >= 3) return `${d.slice(0, 2)}/${d.slice(2)}`;
  return d.length === 2 && prev.length < v.length ? `${d}/` : d;
};

export default function Checkout() {
  const { cart, refresh } = useCart();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState<CheckoutInput>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const v = useFormValidation("checkout");
  const tracked = useRef(false);

  // Signed-in shoppers: start with their name and email.
  useEffect(() => {
    if (user) setForm((f) => ({ ...f, full_name: f.full_name || user.name, email: f.email || user.email, card_name: f.card_name || user.name }));
  }, [user?.id]);

  useEffect(() => {
    if (cart && cart.item_count > 0 && !tracked.current) {
      tracked.current = true;
      track({ type: "checkout_started" });
    }
  }, [cart]);

  if (!cart) return <div className="container page"><div className="skeleton-detail" /></div>;
  if (cart.item_count === 0)
    return (
      <div className="container page">
        <div className="empty-state">
          <div className="empty-state-icon">🛍️</div>
          <h2>Your cart is empty</h2>
          <p className="muted">Add something to your cart before checking out.</p>
          <Link to="/products" className="btn btn-primary">
            Browse products
          </Link>
        </div>
      </div>
    );

  const set = (key: keyof CheckoutInput, value: string, also: string[] = []) => {
    const next = { ...form, [key]: value };
    setForm(next);
    v.change(key, next as unknown as Record<string, string>, also);
  };
  const props = (key: keyof CheckoutInput, extra: Partial<React.InputHTMLAttributes<HTMLInputElement>> = {}) => ({
    name: key,
    value: form[key],
    error: v.errors[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => set(key, e.target.value),
    onBlur: () => v.blur(key, form as unknown as Record<string, string>),
    ...extra,
  });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const order = await placeOrder(form);
      refreshCatalogue(); // stock just changed
      await refresh();
      navigate(`/order/${order.order_number}`, { state: { order }, replace: true });
    } catch (err) {
      if (v.fromError(err)) setError("Please fix the highlighted fields.");
      else setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setBusy(false);
    }
  };

  const brand = v.hints.card_brand;
  const errorCount = Object.keys(v.errors).length;

  return (
    <div className="container page">
      <div className="page-head">
        <h1>Checkout</h1>
        <p className="muted">Every field is checked as you go, so you can fix anything before placing your order.</p>
      </div>
      <form className="checkout-layout" onSubmit={submit} noValidate>
        <div className="checkout-form">
          {error && (
            <div className="alert" role="alert">
              {error} {errorCount > 0 && `(${errorCount} field${errorCount === 1 ? "" : "s"})`}
            </div>
          )}
          <section className="form-section">
            <h3><span>1</span> Contact</h3>
            <Field label="Full name" autoComplete="name" placeholder="Handsome Dan" {...props("full_name")} />
            <div className="form-row">
              <Field label="Email" type="email" autoComplete="email" placeholder="you@yale.edu" {...props("email")} />
              <Field label="Phone" type="tel" autoComplete="tel" placeholder="(203) 555-0123" hint="10-digit US number" {...props("phone")} />
            </div>
          </section>

          <section className="form-section">
            <h3><span>2</span> Shipping address</h3>
            <Field label="Street address" autoComplete="address-line1" placeholder="149 Elm St" {...props("address1")} />
            <Field label="Apartment, suite, etc. (optional)" autoComplete="address-line2" placeholder="Apt 4B" {...props("address2")} />
            <div className="form-row three">
              <Field label="City" autoComplete="address-level2" placeholder="New Haven" {...props("city")} />
              <Field label="State" autoComplete="address-level1" placeholder="CT" maxLength={2} {...props("state", { onChange: (e) => set("state", e.target.value.toUpperCase().slice(0, 2)) })} />
              <Field label="ZIP code" autoComplete="postal-code" inputMode="numeric" placeholder="06511" maxLength={10} {...props("zip")} />
            </div>
          </section>

          <section className="form-section">
            <h3><span>3</span> Payment</h3>
            <p className="demo-note">🧪 Demo checkout: no card is charged. We check the card format, then keep only the card brand and last 4 digits. Try the test card 4242 4242 4242 4242.</p>
            <Field label="Name on card" autoComplete="cc-name" {...props("card_name")} />
            <Field
              label="Card number"
              inputMode="numeric"
              autoComplete="cc-number"
              placeholder="1234 5678 9012 3456"
              hint="Visa, Mastercard, American Express, or Discover"
              {...props("card_number", { onChange: (e) => set("card_number", formatCard(e.target.value), ["cvv"]) })}
            >
              {brand && <span className="card-brand">{brand}</span>}
            </Field>
            <div className="form-row">
              <Field label="Expiration (MM/YY)" inputMode="numeric" autoComplete="cc-exp" placeholder="08/28" maxLength={5} {...props("expiry", { onChange: (e) => set("expiry", formatExpiry(e.target.value, form.expiry)) })} />
              <Field label="Security code (CVV)" inputMode="numeric" autoComplete="cc-csc" placeholder={brand === "American Express" ? "4 digits" : "3 digits"} maxLength={4} {...props("cvv", { onChange: (e) => set("cvv", e.target.value.replace(/\D/g, "").slice(0, 4)) })} />
            </div>
          </section>
        </div>

        <aside className="summary-card checkout-summary">
          <h3>Order summary</h3>
          <ul className="summary-items">
            {cart.items.filter((i) => i.available > 0).map((i) => (
              <li key={`${i.product_id}-${i.size}`}>
                <div className="summary-thumb">
                  <img src={i.thumb_url} alt="" />
                  <span>{i.quantity}</span>
                </div>
                <div>
                  <strong>{i.name}</strong>
                  <span>Size {i.size}</span>
                </div>
                <span>{formatPrice(i.line_total)}</span>
              </li>
            ))}
          </ul>
          <OrderSummary cart={cart} />
          <button className="btn btn-primary full" type="submit" disabled={busy}>
            {busy ? "Placing order…" : `Place order · ${formatPrice(cart.total)}`}
          </button>
          <Link to="/cart" className="summary-edit">
            Edit cart
          </Link>
        </aside>
      </form>
    </div>
  );
}
