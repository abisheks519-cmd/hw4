import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { useCart } from "../cart";
import SearchBar from "./SearchBar";

const ANNOUNCEMENTS = [
  "Free shipping on orders over $75",
  "New: compare up to 4 styles side by side",
  "Questions about sizes or stock? Ask our shopping assistant",
];

const LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/products", label: "Products" },
  { to: "/about", label: "About Us" },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const { user, logout } = useAuth();
  const { count, openDrawer } = useCart();
  const navigate = useNavigate();
  const close = () => setOpen(false);
  const [scrolled, setScrolled] = useState(false);
  const headerRef = useRef<HTMLElement>(null);

  // Publish the header's height (it grows when the search bar wraps on smaller screens) so
  // sticky bars like the Products filters can sit right under it.
  useEffect(() => {
    const el = headerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => document.documentElement.style.setProperty("--header-h", `${el.offsetHeight}px`));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const [note, setNote] = useState(0);

  // The glass header gets a firmer background and shadow once the page scrolls under it.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    const t = setInterval(() => setNote((n) => (n + 1) % ANNOUNCEMENTS.length), 4500);
    return () => clearInterval(t);
  }, []);
  const handleLogout = async () => {
    close();
    await logout();
    navigate("/logout");
  };

  return (
    <header ref={headerRef} className={`site-header ${scrolled ? "scrolled" : ""}`}>
      <div className="announcement" aria-live="polite">
        <span key={note}>{ANNOUNCEMENTS[note]}</span>
      </div>
      <nav className="navbar">
        <Link to="/" className="brand" onClick={close}>
          <span className="brand-mark">CC</span>
          <span className="brand-name">Campus Customs</span>
        </Link>
        <SearchBar />
        <button className="cart-btn" onClick={() => { close(); openDrawer(); }} aria-label={`Cart, ${count} item${count === 1 ? "" : "s"}`}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 7h12l-1.2 12.1a1 1 0 0 1-1 .9H8.2a1 1 0 0 1-1-.9L6 7Z" />
            <path d="M9 7V6a3 3 0 0 1 6 0v1" />
          </svg>
          {count > 0 && <span className="cart-badge">{count > 99 ? "99+" : count}</span>}
        </button>
        <button className="menu-toggle" aria-label="Toggle menu" onClick={() => setOpen(!open)}>
          ☰
        </button>
        <div className={`nav-links ${open ? "open" : ""}`}>
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} onClick={close}>
              {l.label}
            </NavLink>
          ))}
          <span className="nav-divider" />
          {user ? (
            <>
              {user.is_admin && (
                <NavLink to="/admin" className="nav-admin" onClick={close}>
                  📊 Dashboard
                </NavLink>
              )}
              <span className="nav-user">Hi, {user.first_name || user.name}</span>
              <button className="nav-cta nav-logout" onClick={handleLogout}>
                Log Out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" onClick={close}>
                Login
              </NavLink>
              <NavLink to="/create-account" className="nav-cta" onClick={close}>
                Create Account
              </NavLink>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
