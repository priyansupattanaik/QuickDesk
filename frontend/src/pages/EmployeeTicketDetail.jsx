import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import client from "../api/client";

export default function EmployeeTicketDetail() {
  const { id } = useParams();
  const [ticket, setTicket] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    client
      .get(`/api/tickets/${id}`)
      .then(({ data }) => setTicket(data))
      .catch((err) => setError(err.response?.data?.detail || "Unable to load ticket"));
  }, [id]);

  if (error && !ticket) {
    return (
      <section className="page-container">
        <div className="form-error" role="alert">{error}</div>
        <Link to="/tickets/mine" className="back-link">
          <ArrowLeft size={16} /> Back to my tickets
        </Link>
      </section>
    );
  }

  if (!ticket) return <div className="loading-state">Loading ticket...</div>;

  return (
    <section className="page-container">
      <div className="detail-top-nav">
        <Link to="/tickets/mine" className="back-link">
          <ArrowLeft size={16} /> Back to my tickets
        </Link>
      </div>

      <div className="ticket-header-group">
        <div className="ticket-title-row">
          <span className="ticket-id">#{ticket.id}</span>
          <h1 className="ticket-heading">{ticket.title}</h1>
        </div>
        <div className="status-indicator status-flip" key={ticket.status}>
          <span
            className={`dot ${
              ticket.status === "Open" ? "dot-open" : "dot-resolved"
            }`}
          />
          {ticket.status}
        </div>
      </div>

      <div className="detail-section">
        <h2 className="section-title">Your request</h2>
        <div className="request-body">{ticket.description}</div>

        <div className="meta-list">
          <div className="meta-row">
            <span className="meta-label">Submitted</span>
            <span className="meta-val">
              {new Date(ticket.created_at).toLocaleString()}
            </span>
          </div>
          <div className="meta-row">
            <span className="meta-label">Category</span>
            <span className="meta-val">{ticket.final_category}</span>
          </div>
          <div className="meta-row">
            <span className="meta-label">Attachment name</span>
            <span className="meta-val">
              {ticket.attachment_filename || "None"}
            </span>
          </div>
        </div>
      </div>

      {ticket.status === "Resolved" ? (
        <div className="detail-section">
          <h2 className="section-title">Support reply</h2>
          <div className="reply-content">{ticket.final_reply}</div>
          {ticket.resolved_at && (
            <div className="resolved-timestamp">
              Resolved {new Date(ticket.resolved_at).toLocaleString()}
            </div>
          )}
        </div>
      ) : (
        <div className="detail-section">
          <h2 className="section-title">Status</h2>
          <p className="status-note">
            Your ticket is currently open. A support agent will review and reply here.
          </p>
        </div>
      )}
    </section>
  );
}
