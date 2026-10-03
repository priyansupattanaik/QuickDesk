import { useCallback, useEffect, useState } from "react";
import client from "../api/client";

function duration(seconds) {
  if (seconds == null) return "No resolved tickets yet";
  const total = Math.round(seconds); const hours = Math.floor(total / 3600); const minutes = Math.floor((total % 3600) / 60); const secs = total % 60;
  return hours ? `${hours}h ${minutes}m` : `${minutes}m ${secs}s`;
}

export default function Metrics() {
  const [data, setData] = useState(null); const [error, setError] = useState("");
  const load = useCallback(() => { client.get("/api/metrics").then(({ data: next }) => setData(next)).catch(() => setError("Unable to load metrics")); }, []);
  useEffect(() => { load(); }, [load]); // Metrics stay manual; live updates are deliberately out of scope.
  const max = Math.max(1, ...(data?.by_category || []).map((row) => row.count));
  return <section className="content wide"><div className="eyebrow">AGENT SPACE / METRICS</div><div className="section-heading"><h1>Support metrics.</h1><button className="secondary" onClick={load}>Refresh</button></div>{error && <p className="error">{error}</p>}{data && <><div className="metric-grid"><div className="metric-card"><span>Open</span><strong>{data.by_status.Open}</strong></div><div className="metric-card"><span>Resolved</span><strong>{data.by_status.Resolved}</strong></div><div className="metric-card"><span>Median resolution</span><strong>{duration(data.median_resolution_seconds)}</strong></div><div className="metric-card"><span>AI override rate</span><strong>{data.override_rate_percent == null ? "—" : `${data.override_rate_percent.toFixed(1)}%`}</strong></div></div><div className="detail-card"><h2>Tickets by category</h2><div className="metric-bars">{data.by_category.map((row) => <div className="metric-bar-row" key={row.category}><span>{row.category} — {row.count}</span><i style={{ width: `${(row.count / max) * 100}%` }} /></div>)}</div></div></>}</section>;
}
