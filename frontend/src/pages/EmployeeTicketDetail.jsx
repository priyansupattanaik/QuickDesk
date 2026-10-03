import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
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
      <section className="content">
        <p className="error">{error}</p>
        <Link to="/tickets/mine">Back to my tickets</Link>
      </section>
    );
  }
  if (!ticket) return <div className="loading">Loading ticket...</div>;

  return (
    <section className="content wide">
      <div className="eyebrow">SUPPORT / MY TICKET</div>
      <div className="detail-heading">
        <h1>{ticket.title}</h1>
        <span className={`badge ${ticket.status.toLowerCase()}`}>{ticket.status}</span>
      </div>
      <p className="muted">
        <Link to="/tickets/mine">← Back to my tickets</Link>
      </p>
      <div className="detail-card">
        <h2>Your request</h2>
        <p>{ticket.description}</p>
        <div className="detail-grid">
          <span>
            <b>Submitted</b>
            {new Date(ticket.created_at).toLocaleString()}
          </span>
          <span>
            <b>Category</b>
            {ticket.final_category}
          </span>
          <span>
            <b>Priority</b>
            {ticket.final_priority}
          </span>
          <span>
            <b>Attachment</b>
            {ticket.attachment_filename || "None"}
          </span>
        </div>
      </div>
      {ticket.status === "Resolved" ? (
        <div className="detail-card">
          <h2>Support reply</h2>
          <p>{ticket.final_reply}</p>
          {ticket.resolved_at && (
            <p className="muted">Resolved {new Date(ticket.resolved_at).toLocaleString()}</p>
          )}
        </div>
      ) : (
        <div className="detail-card">
          <h2>Status</h2>
          <p className="muted">Your ticket is open. An agent will respond here when it is resolved.</p>
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}
