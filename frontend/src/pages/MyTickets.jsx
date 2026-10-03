import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import client from "../api/client";
import useTicketEvents from "../realtime/useTicketEvents";

export default function MyTickets() {
  const [tickets, setTickets] = useState([]); const [error, setError] = useState("");
  const loadTickets = useCallback(() => { client.get("/api/tickets/mine").then(({ data }) => setTickets(data)).catch(() => setError("Unable to load tickets")); }, []);
  useEffect(() => { loadTickets(); }, [loadTickets]);
  useTicketEvents({ onOpen: loadTickets, onTicketResolved: loadTickets }); // Reconnect open refetches the source of truth after a dropped stream.
  return <section className="content wide"><div className="eyebrow">SUPPORT / MY TICKETS</div><h1>Your tickets.</h1><p className="lead">This view refreshes when opened and when a reply resolves one of your tickets.</p>{error && <p className="error">{error}</p>}<div className="ticket-list">{tickets.length ? tickets.map((ticket) => <Link className="ticket-row" to={`/tickets/mine/${ticket.id}`} key={ticket.id}><div><strong>{ticket.title}</strong><span className="muted">{new Date(ticket.created_at).toLocaleDateString()}</span></div><div className="ticket-meta"><span className={`badge ${ticket.status.toLowerCase()}`}>{ticket.status}</span><span className="chip">{ticket.final_category}</span><span className="chip">{ticket.final_priority}</span></div></Link>) : <div className="empty-card">No tickets yet.</div>}</div></section>;
}
