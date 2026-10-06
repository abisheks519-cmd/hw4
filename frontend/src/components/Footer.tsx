import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div>
          <div className="brand footer-brand">
            <span className="brand-mark">CC</span>
            <span className="brand-name">Campus Customs</span>
          </div>
          <p>High quality campus merchandise at affordable prices.</p>
        </div>
        <div>
          <h4>Shop</h4>
          <Link to="/products">All Products</Link>
          <Link to="/products?category=Hoodies">Hoodies</Link>
          <Link to="/products?category=T-Shirts">T-Shirts</Link>
          <Link to="/compare">Compare products</Link>
          <Link to="/cart">Your cart</Link>
        </div>
        <div>
          <h4>Company</h4>
          <Link to="/about">About Us</Link>
          <Link to="/login">Login</Link>
          <Link to="/create-account">Create Account</Link>
        </div>
      </div>
      <div className="footer-wordmark" aria-hidden="true">Campus Customs</div>
      <div className="footer-bottom">© {new Date().getFullYear()} Campus Customs · High quality campus apparel at affordable prices</div>
    </footer>
  );
}
