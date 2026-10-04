import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import client from "../api/client";

export default function Dashboard() {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    if (user?.role === "agent") {
      client
        .get("/api/agents/summary")
        .then(({ data }) => setSummary(data))
        .catch(() => {});
    }
  }, [user]);

  const isAgent = user?.role === "agent";

  return (
    <section className="page-container">
      <header className="page-header">
        <h1 className="page-title">
          Welcome, {user?.full_name?.split(" ")[0] || "User"}.
        </h1>
      </header>

      <div className="overview-card">
        <p className="overview-user-info">
          Signed in as <strong>{user?.email}</strong> ({user?.role}).
        </p>

        <div className="overview-status-item">
          <span className="dot dot-resolved" />
          <span>Internal support desk is online and active.</span>
        </div>

        {summary && (
          <div className="overview-status-item">
            <span>
              <strong>{summary.total_agents}</strong> agent account
              {summary.total_agents === 1 ? "" : "s"} active.
            </span>
          </div>
        )}

        <div className="overview-actions">
          {isAgent ? (
            <Link to="/dashboard" className="primary btn-primary">
              View Queue
            </Link>
          ) : (
            <Link to="/tickets/mine" className="primary btn-primary">
              View My Tickets
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
