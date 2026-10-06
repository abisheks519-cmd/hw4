import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section className="page narrow center">
      <h1>Page not found</h1>
      <p className="muted">The page you're looking for doesn't exist.</p>
      <Link to="/" className="btn btn-primary">
        Back to Home
      </Link>
    </section>
  );
}
