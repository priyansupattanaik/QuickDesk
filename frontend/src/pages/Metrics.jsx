import { useCallback, useEffect, useState } from "react";
import client from "../api/client";

function formatDuration(seconds) {
  if (seconds == null) return "—";
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

export default function Metrics() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadMetrics = useCallback(() => {
    setLoading(true);
    client
      .get("/api/metrics")
      .then(({ data: next }) => {
        setData(next);
        setError("");
      })
      .catch(() => setError("Unable to load metrics"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  const maxCategoryCount = Math.max(
    1,
    ...(data?.by_category || []).map((row) => row.count)
  );

  return (
    <section className="page-container wide">
      <header className="page-header">
        <h1 className="page-title">Metrics</h1>
        <button
          type="button"
          className="btn-secondary"
          onClick={loadMetrics}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {error && <div className="form-error" role="alert">{error}</div>}

      {data && (
        <div className="metrics-body">
          <div className="metric-row-four">
            <div className="metric-stat">
              <span className="metric-label">Open</span>
              <strong className="metric-value">{data.by_status.Open ?? 0}</strong>
            </div>

            <div className="metric-stat">
              <span className="metric-label">Resolved</span>
              <strong className="metric-value">{data.by_status.Resolved ?? 0}</strong>
            </div>

            <div className="metric-stat">
              <span className="metric-label">Median time</span>
              <strong className="metric-value">
                {formatDuration(data.median_resolution_seconds)}
              </strong>
            </div>

            <div className="metric-stat">
              <span className="metric-label">Category-override rate</span>
              <strong className="metric-value">
                {data.override_rate_percent == null
                  ? "—"
                  : `${data.override_rate_percent.toFixed(1)}%`}
              </strong>
            </div>
          </div>

          <div className="metric-section">
            <h2 className="section-title">Category breakdown</h2>
            <div className="bar-list">
              {data.by_category.map((row) => (
                <div key={row.category} className="bar-list-row">
                  <div className="bar-row-labels">
                    <span className="bar-name">{row.category}</span>
                    <span className="bar-count">{row.count}</span>
                  </div>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{
                        width: `${(row.count / maxCategoryCount) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
