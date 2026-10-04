import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import client from "../api/client";
import useTicketEvents from "../realtime/useTicketEvents";

export default function AgentDashboard() {
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 20 });
  const [search, setSearch] = useState(params.get("q") || "");
  const [error, setError] = useState("");
  const [liveTicketId, setLiveTicketId] = useState(null);

  const status = params.get("status") || "";
  const category = params.get("category") || "";
  const priority = params.get("priority") || "";
  const page = Number(params.get("page") || 1);

  const requestId = useRef(0);

  const loadTickets = useCallback(() => {
    const id = ++requestId.current;
    client
      .get(`/api/tickets?${params.toString()}`)
      .then(({ data: next }) => {
        if (id !== requestId.current) return;
        setError("");
        setData(next);
      })
      .catch(() => {
        if (id !== requestId.current) return;
        setError("Unable to load tickets");
      });
  }, [params]);

  useEffect(() => {
    const timer = setTimeout(() => {
      const query = new URLSearchParams(params);
      if (search) query.set("q", search);
      else query.delete("q");
      query.set("page", "1");
      setParams(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  const handleTicketCreated = useCallback((event) => {
    const query = (params.get("q") || "").toLowerCase();
    const visible =
      page <= 1 &&
      (!status || event?.status === status) &&
      (!category || event?.ai_category === category) &&
      (!priority || event?.ai_priority === priority) &&
      (!query || String(event?.title || "").toLowerCase().includes(query));
    if (visible && event?.id) {
      setData((current) => {
        if (current.items.some((item) => item.id === event.id)) return current;
        const row = {
          id: event.id,
          title: event.title,
          status: event.status,
          ai_category: event.ai_category,
          ai_priority: event.ai_priority,
          final_category: event.ai_category,
          final_priority: event.ai_priority,
          created_at: event.created_at,
          employee: { email: event.employee_email },
        };
        return {
          ...current,
          items: [row, ...current.items].slice(0, current.page_size || 20),
          total: current.total + 1,
        };
      });
      setLiveTicketId(event.id);
      window.setTimeout(() => setLiveTicketId((current) => (current === event.id ? null : current)), 1600);
    }
    loadTickets();
  }, [category, loadTickets, page, params, priority, status]);

  useTicketEvents({
    onOpen: loadTickets,
    onTicketCreated: handleTicketCreated,
  });

  const setFilter = (key, value) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.set("page", "1");
    setParams(next);
  };

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <section className="page-container wide">
      <header className="page-header">
        <h1 className="page-title">Queue</h1>
      </header>

      <div className="filter-row">
        <div className="search-input-wrap">
          <Search size={16} className="search-icon" aria-hidden="true" />
          <input
            type="search"
            placeholder="Search titles..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="filter-search"
            aria-label="Search ticket titles"
          />
        </div>

        <select
          value={status}
          onChange={(e) => setFilter("status", e.target.value)}
          className="filter-select"
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="Open">Open</option>
          <option value="Resolved">Resolved</option>
        </select>

        <select
          value={category}
          onChange={(e) => setFilter("category", e.target.value)}
          className="filter-select"
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {["IT", "HR", "Finance", "Admin", "Other"].map((val) => (
            <option key={val} value={val}>{val}</option>
          ))}
        </select>

        <select
          value={priority}
          onChange={(e) => setFilter("priority", e.target.value)}
          className="filter-select"
          aria-label="Filter by priority"
        >
          <option value="">All priorities</option>
          {["Low", "Medium", "High"].map((val) => (
            <option key={val} value={val}>{val}</option>
          ))}
        </select>
      </div>

      {error && <div className="form-error" role="alert">{error}</div>}

      <div className="queue-list-wrapper">
        <div className="queue-list">
          {data.items.length === 0 ? (
            <div className="empty-state">
              <p className="empty-text">No matching tickets.</p>
            </div>
          ) : (
            data.items.map((ticket) => {
              const categoryChanged =
                ticket.ai_category && ticket.final_category !== ticket.ai_category;
              const priorityChanged =
                ticket.ai_priority && ticket.final_priority !== ticket.ai_priority;
              const isLive = ticket.id === liveTicketId;

              return (
                <Link
                  key={ticket.id}
                  to={`/tickets/${ticket.id}`}
                  className={`queue-list-row ${isLive ? "live-highlight" : ""}`}
                >
                  <div className="queue-col-main">
                    <span className="ticket-id">#{ticket.id}</span>
                    <span className="queue-title">{ticket.title}</span>
                  </div>

                  <div className="queue-col-sender" title={ticket.employee?.email}>
                    {ticket.employee?.email}
                  </div>

                  <div className="queue-col-category">
                    <span className="val-text">{ticket.final_category}</span>
                    {categoryChanged && <span className="changed-mark">changed</span>}
                  </div>

                  <div className="queue-col-priority">
                    <span
                      className={`val-text ${
                        ticket.final_priority === "High" ? "priority-high" : ""
                      }`}
                    >
                      {ticket.final_priority}
                    </span>
                    {priorityChanged && <span className="changed-mark">changed</span>}
                  </div>

                  <div className="queue-col-status">
                    <span className="status-indicator status-flip" key={ticket.status}>
                      <span
                        className={`dot ${
                          ticket.status === "Open" ? "dot-open" : "dot-resolved"
                        }`}
                      />
                      {ticket.status}
                    </span>
                  </div>

                  <div className="queue-col-date">
                    {new Date(ticket.created_at).toLocaleDateString()}
                  </div>
                </Link>
              );
            })
          )}
        </div>
      </div>

      <div className="pagination">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => setFilter("page", String(page - 1))}
          className="btn-secondary"
        >
          Previous
        </button>
        <span className="pagination-info">
          Page {data.page} of {totalPages}
        </span>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => setFilter("page", String(page + 1))}
          className="btn-secondary"
        >
          Next
        </button>
      </div>
    </section>
  );
}
