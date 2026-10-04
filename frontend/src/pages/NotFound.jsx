import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section className="page-container">
      <h1 className="page-title">Page not found</h1>
      <p className="notfound-message">
        The requested page does not exist or has moved.
      </p>
      <Link to="/" className="btn-secondary">
        Return to workspace
      </Link>
    </section>
  );
}
