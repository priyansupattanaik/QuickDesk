import { useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";

export default function NewTicket() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ title: "", description: "", attachment_filename: "" });
  const [error, setError] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    setError("");
    try { await client.post("/api/tickets", { ...form, attachment_filename: form.attachment_filename || null }); navigate("/tickets/mine"); }
    catch (err) { setError(err.response?.data?.detail || "Unable to submit ticket"); }
  };
  return <section className="content wide"><div className="eyebrow">SUPPORT / NEW TICKET</div><h1>Tell us what needs attention.</h1><p className="lead">Include enough detail for the support team to start investigating.</p><form className="ticket-form" onSubmit={submit}><label>Title<input maxLength="200" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label><label>Description<textarea maxLength="5000" required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label><label>Attachment filename <span className="muted">(optional; no upload)</span><input maxLength="255" value={form.attachment_filename} onChange={(e) => setForm({ ...form, attachment_filename: e.target.value })} /></label>{error && <p className="error">{error}</p>}<button className="primary">Submit ticket</button></form></section>;
}
