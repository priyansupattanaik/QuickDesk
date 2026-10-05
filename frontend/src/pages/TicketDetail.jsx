import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import client from "../api/client";

export default function TicketDetail() {
  const { id } = useParams();
  const [ticket, setTicket] = useState(null);
  const [draft, setDraft] = useState("");
  const [citations, setCitations] = useState([]);
  const [finalCategory, setFinalCategory] = useState("");
  const [finalPriority, setFinalPriority] = useState("");
  const [loading, setLoading] = useState(false);
  const [savingField, setSavingField] = useState(false);
  const [fieldSaved, setFieldSaved] = useState(false);
  const [replySent, setReplySent] = useState(false);
  const [error, setError] = useState("");
  const editorRef = useRef(null);

  const loadTicket = () =>
    client
      .get(`/api/tickets/${id}`)
      .then(async ({ data }) => {
        setTicket(data);
        sessionStorage.setItem("quickdesk_last_agent_ticket", String(data.id));
        setFinalCategory(data.final_category);
        setFinalPriority(data.final_priority);
        if (data.status === "Open" && !data.ai_draft) {
          setLoading(true);
          try {
            const { data: draftData } = await client.post(`/api/tickets/${id}/ai-draft`);
            setDraft(draftData.ai_draft || "");
            setCitations(draftData.citations || []);
            setTicket((prev) => ({
              ...prev,
              ai_draft: draftData.ai_draft,
              ai_citations: draftData.citations,
            }));
          } catch {
            setDraft("");
            setCitations([]);
          } finally {
            setLoading(false);
          }
        } else {
          setDraft(data.ai_draft || "");
          setCitations(data.ai_citations || []);
        }
      })
      .catch((err) => setError(err.response?.data?.detail || "Unable to load ticket"));

  useEffect(() => {
    loadTicket();
  }, [id]);

  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.style.height = "auto";
      editorRef.current.style.height = `${Math.max(140, editorRef.current.scrollHeight)}px`;
    }
  }, [draft]);

  const generateDraft = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await client.post(`/api/tickets/${id}/ai-draft`);
      setDraft(data.ai_draft);
      setCitations(data.citations);
      setTicket((prev) => ({
        ...prev,
        ai_draft: data.ai_draft,
        ai_citations: data.citations,
      }));
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to generate draft");
    } finally {
      setLoading(false);
    }
  };

  const saveOverride = async () => {
    setSavingField(true);
    setError("");
    setFieldSaved(false);
    try {
      await client.patch(`/api/tickets/${id}/classification`, {
        final_category: finalCategory,
        final_priority: finalPriority,
      });
      await loadTicket();
      setFieldSaved(true);
      setTimeout(() => setFieldSaved(false), 1500);
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to save override");
    } finally {
      setSavingField(false);
    }
  };

  const send = async () => {
    setLoading(true);
    setError("");
    const currentDraft = draft;
    try {
      const { data } = await client.post(`/api/tickets/${id}/reply`, {
        reply_text: draft,
      });
      setTicket({
        ...data,
        ai_draft: data.ai_draft || ticket?.ai_draft || currentDraft,
        ai_citations: data.ai_citations || citations,
      });
      setReplySent(true);
      setTimeout(() => setReplySent(false), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to send reply");
    } finally {
      setLoading(false);
    }
  };

  if (error && !ticket) {
    return (
      <section className="page-container">
        <div className="form-error" role="alert">{error}</div>
        <Link to="/dashboard" className="back-link">
          <ArrowLeft size={16} /> Back to queue
        </Link>
      </section>
    );
  }

  if (!ticket) return <div className="loading-state">Loading ticket...</div>;

  const isOpen = ticket.status === "Open";

  return (
    <section className="page-container wide">
      <div className="detail-top-nav">
        <Link to="/dashboard" className="back-link">
          <ArrowLeft size={16} /> Back to queue
        </Link>
      </div>

      <div className="ticket-detail-grid">
        {/* Left Column: Request, Who sent it, Editable category & priority */}
        <div className="detail-col-left">
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
            <h2 className="section-title">Request</h2>
            <div className="request-body">{ticket.description}</div>
          </div>

          <div className="detail-section">
            <h2 className="section-title">Sender</h2>
            <div className="meta-list">
              <div className="meta-row">
                <span className="meta-label">Submitted by</span>
                <span className="meta-val">
                  {ticket.employee?.full_name
                    ? `${ticket.employee.full_name} (${ticket.employee?.email})`
                    : ticket.employee?.email}
                </span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Created</span>
                <span className="meta-val">
                  {new Date(ticket.created_at).toLocaleString()}
                </span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Attachment name</span>
                <span className="meta-val">
                  {ticket.attachment_filename || "None"}
                </span>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <h2 className="section-title">Classification</h2>
            <div className="classification-form">
              <div className="form-group">
                <label htmlFor="edit-category">Category</label>
                <select
                  id="edit-category"
                  value={finalCategory}
                  onChange={(e) => setFinalCategory(e.target.value)}
                  disabled={savingField}
                  className="detail-select"
                >
                  {["IT", "HR", "Finance", "Admin", "Other"].map((val) => (
                    <option key={val} value={val}>{val}</option>
                  ))}
                </select>
                {ticket.ai_category && (
                  <div className="field-suggestion-line">
                    <span className="chip-suggested">suggested</span>
                    {ticket.ai_confidence != null && (
                      <span className="chip-suggested" style={{ marginLeft: "4px" }}>
                        {ticket.ai_confidence}% confident
                      </span>
                    )}
                    {finalCategory !== ticket.ai_category && (
                      <span className="changed-mark">originally {ticket.ai_category}</span>
                    )}
                  </div>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="edit-priority">Priority</label>
                <select
                  id="edit-priority"
                  value={finalPriority}
                  onChange={(e) => setFinalPriority(e.target.value)}
                  disabled={savingField}
                  className="detail-select"
                >
                  {["Low", "Medium", "High"].map((val) => (
                    <option key={val} value={val}>{val}</option>
                  ))}
                </select>
                {ticket.ai_priority && (
                  <div className="field-suggestion-line">
                    <span className="chip-suggested">suggested</span>
                    {ticket.ai_confidence != null && (
                      <span className="chip-suggested" style={{ marginLeft: "4px" }}>
                        {ticket.ai_confidence}% confident
                      </span>
                    )}
                    {finalPriority !== ticket.ai_priority && (
                      <span className="changed-mark">originally {ticket.ai_priority}</span>
                    )}
                  </div>
                )}
              </div>

              <div className="save-override-action">
                <button
                  type="button"
                  onClick={saveOverride}
                  disabled={savingField}
                  className="btn-secondary"
                >
                  {savingField ? "Saving..." : "Save classification"}
                </button>
                {fieldSaved && (
                  <span className="save-indicator" role="status">Saved</span>
                )}
              </div>
            </div>
          </div>

          {ticket.audit_log && ticket.audit_log.length > 0 && (
            <div className="detail-section">
              <h2 className="section-title">History</h2>
              <div className="audit-list">
                {ticket.audit_log.map((entry) => (
                  <div key={entry.id} className="audit-item">
                    <span>{entry.agent?.email} changed {entry.field} from {entry.from_value} to {entry.to_value}</span>
                    <span className="audit-time">{new Date(entry.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: The Reply, AI Draft, Citations, Send Reply at bottom */}
        <div className="detail-col-right">
          {isOpen ? (
            <div className="reply-editor-pane">
              <div className="reply-pane-header">
                <h2 className="section-title">Reply</h2>
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={generateDraft}
                  disabled={loading}
                >
                  {loading ? "Generating..." : "Regenerate draft"}
                </button>
              </div>

              <div className="editor-wrap">
                <textarea
                  ref={editorRef}
                  className="reply-textarea"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="The AI draft loads here, or write a custom reply..."
                  rows={8}
                />
              </div>

              {citations && citations.length > 0 && (
                <div className="citations-container">
                  <span className="citations-label">Citations</span>
                  <div className="citations-list">
                    {citations.map((c, i) => (
                      c.article_id ? (
                        <Link key={c.article_id || i} to={`/kb/${c.article_id}`} className="citation-title">
                          <span>{c.title || "Knowledge-base article"}</span>
                          <span className="citation-open">Open source</span>
                        </Link>
                      ) : <div key={i} className="citation-title">{c.title || c}</div>
                    ))}
                  </div>
                </div>
              )}

              {error && <div className="form-error" role="alert">{error}</div>}

              <div className="send-bottom-pinned">
                <button
                  type="button"
                  className="primary btn-primary"
                  disabled={!draft.trim() || loading}
                  onClick={send}
                >
                  {loading ? "Sending..." : "Send reply"}
                </button>
                {replySent && <span className="save-indicator" role="status" style={{ marginLeft: "12px", color: "var(--color-text-muted)" }}>Notification sent</span>}
              </div>
            </div>
          ) : (
            <div className="stacked-replies-pane">
              <div className="reply-block">
                <div className="reply-label">Final reply</div>
                <div className="reply-content">{ticket.final_reply}</div>
              </div>

              <div className="reply-block">
                <div className="reply-label">AI draft</div>
                <div className="reply-content">
                  {ticket.ai_draft || draft || "No AI draft recorded."}
                </div>
                {citations && citations.length > 0 && (
                  <div className="citations-container">
                    <span className="citations-label">Citations</span>
                    <div className="citations-list">
                      {citations.map((c, i) => (
                        c.article_id ? (
                          <Link key={c.article_id || i} to={`/kb/${c.article_id}`} className="citation-title">
                            <span>{c.title || "Knowledge-base article"}</span>
                            <span className="citation-open">Open source</span>
                          </Link>
                        ) : <div key={i} className="citation-title">{c.title || c}</div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
