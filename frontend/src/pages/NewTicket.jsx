import { useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";

export default function NewTicket() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    title: "",
    description: "",
    attachment_filename: "",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await client.post("/api/tickets", {
        ...form,
        attachment_filename: form.attachment_filename.trim() || null,
      });
      navigate("/tickets/mine");
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to submit ticket");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="page-container">
      <div className="single-column-form-wrap">
        <h1 className="page-title">New ticket</h1>
        <form onSubmit={submit} className="form-column" noValidate>
          <div className="form-group">
            <label htmlFor="ticket-title">Title</label>
            <input
              id="ticket-title"
              maxLength={200}
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label htmlFor="ticket-desc">Description</label>
            <textarea
              id="ticket-desc"
              rows={6}
              maxLength={5000}
              required
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label htmlFor="ticket-attachment">Attachment name</label>
            <input
              id="ticket-attachment"
              maxLength={255}
              value={form.attachment_filename}
              onChange={(e) =>
                setForm({ ...form, attachment_filename: e.target.value })
              }
              placeholder="e.g. system_logs.txt"
            />
          </div>

          {error && <div className="form-error" role="alert">{error}</div>}

          <div className="form-actions">
            <button
              type="submit"
              className="primary btn-primary"
              disabled={submitting}
            >
              {submitting ? "Submitting..." : "Submit"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
