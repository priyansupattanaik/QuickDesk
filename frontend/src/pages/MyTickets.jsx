import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import client from "../api/client";
import useTicketEvents from "../realtime/useTicketEvents";

export default function MyTickets() {
  const [tickets, setTickets] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const requestId = useRef(0);

  const loadTickets = useCallback(() => {
    const id = ++requestId.current;
    client
      .get("/api/tickets/mine")
      .then(({ data }) => {
        if (id !== requestId.current) return;
        setError("");
        setTickets(data);
      })
      .catch(() => {
        if (id !== requestId.current) return;
        setError("Unable to load tickets");
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false);
      });
  }, []);

  const applyResolved = useCallback((event) => {
    if (event?.ticket_id) {
      setTickets((current) =>
        current.map((ticket) =>
          ticket.id === event.ticket_id
            ? { ...ticket, status: event.status || "Resolved", resolved_at: event.resolved_at }
            : ticket
        )
      );
    }
    loadTickets();
  }, [loadTickets]);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  useTicketEvents({ onOpen: loadTickets, onTicketResolved: applyResolved });

  return (
    <section className="page-container">
      <header className="page-header">
        <h1 className="page-title">My Tickets</h1>
        {tickets.length > 0 && (
          <Link to="/tickets/new" className="primary btn-primary">
            New ticket
          </Link>
        )}
      </header>

      {error && <div className="form-error" role="alert">{error}</div>}

      {loading ? (
        <div className="loading-state">Loading tickets...</div>
      ) : tickets.length === 0 ? (
        <div className="empty-state">
          <p className="empty-text">You have not submitted any tickets yet.</p>
          <Link to="/tickets/new" className="primary btn-primary">
            New ticket
          </Link>
        </div>
      ) : (
        <div className="ticket-list-wrapper">
          <div className="ticket-list">
            {tickets.map((ticket) => (
              <Link
                key={ticket.id}
                to={`/tickets/mine/${ticket.id}`}
                className="ticket-list-row"
              >
                <div className="row-main">
                  <span className="ticket-title">{ticket.title}</span>
                </div>
                <div className="row-meta">
                  <span className="status-indicator status-flip" key={ticket.status}>
                    {ticket.status}
                    <span
                      className={`dot ${
                        ticket.status === "Open" ? "dot-open" : "dot-resolved"
                      }`}
                    />
                  </span>
                  <span className="row-category">{ticket.final_category}</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
