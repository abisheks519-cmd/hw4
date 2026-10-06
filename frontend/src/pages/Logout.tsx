import { Link } from "react-router-dom";

export default function Logout() {
  return (
    <div className="logout-page">
      <div className="logout-card">
        <div className="logout-check" aria-hidden="true">
          <svg viewBox="0 0 52 52">
            <circle className="logout-check-circle" cx="26" cy="26" r="24" fill="none" />
            <path className="logout-check-mark" fill="none" d="M14 27l8 8 16-17" />
          </svg>
        </div>
        <h1>You've been logged out</h1>
        <p className="muted">Thanks for visiting Campus Customs. See you again soon!</p>
        <div className="logout-actions">
          <Link to="/" className="btn btn-primary">
            Return Home
          </Link>
          <Link to="/login" className="btn btn-outline">
            Log Back In
          </Link>
        </div>
      </div>
    </div>
  );
}
