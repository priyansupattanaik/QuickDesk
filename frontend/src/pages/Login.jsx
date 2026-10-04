import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const ROLES = [
  {
    id: "employee",
    label: "Employee",
    lede: "Open your tickets and the draft already waiting on them.",
  },
  {
    id: "agent",
    label: "Agent",
    lede: "Open the queue. Agent accounts are issued by the desk.",
  },
];

export function AuthSplitLayout({ title, children }) {
  return (
    <div className="auth-split-screen">
      <div className="auth-split-left">
        <div className="auth-left-content">
          <p className="auth-kicker">QuickDesk</p>
          <p className="auth-statement">Your tickets, with a draft already waiting.</p>
        </div>
      </div>
      <div className="auth-split-right">
        <div className="auth-form-container">
          <h1 className="auth-title">{title}</h1>
          {children}
        </div>
      </div>
    </div>
  );
}

export function PasswordField({
  id,
  label = "Password",
  value,
  onChange,
  invalid,
  describedBy,
  autoComplete = "current-password",
  required = true,
  minLength,
}) {
  const [revealed, setRevealed] = useState(false);

  return (
    <div className="form-group">
      <label htmlFor={id}>{label}</label>
      <div className="password-field">
        <input
          id={id}
          type={revealed ? "text" : "password"}
          name="password"
          autoComplete={autoComplete}
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          required={required}
          minLength={minLength}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          value={value}
          onChange={onChange}
        />
        <button
          type="button"
          className="password-reveal"
          aria-label={revealed ? "Hide password" : "Show password"}
          aria-pressed={revealed}
          onClick={() => setRevealed((prev) => !prev)}
          tabIndex={0}
        >
          {revealed ? (
            <EyeOff size={16} aria-hidden="true" />
          ) : (
            <Eye size={16} aria-hidden="true" />
          )}
        </button>
      </div>
    </div>
  );
}

export default function Login() {
  const { login } = useAuth();
  const [role, setRole] = useState("employee");
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const tabRefs = useRef({});
  const selected = ROLES.find((item) => item.id === role);

  useEffect(() => {
    const active = document.activeElement;
    if (active?.getAttribute("role") === "tab") {
      tabRefs.current[role]?.focus();
    }
  }, [role]);

  const moveRole = (next) => {
    setRole(next);
    setError("");
  };

  const onTabKeyDown = (event) => {
    const index = ROLES.findIndex((item) => item.id === role);
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      moveRole(ROLES[(index + 1) % ROLES.length].id);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      moveRole(ROLES[(index - 1 + ROLES.length) % ROLES.length].id);
    } else if (event.key === "Home") {
      event.preventDefault();
      moveRole(ROLES[0].id);
    } else if (event.key === "End") {
      event.preventDefault();
      moveRole(ROLES[ROLES.length - 1].id);
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(form, role);
    } catch (e) {
      if (e.code === "role_mismatch") {
        const home = e.role === "agent" ? "Agent" : "Employee";
        setError(`This account signs in as ${home}. Switch to the ${home} tab and try again.`);
      } else {
        setError(e.response?.data?.detail || "Unable to sign in. Check the email and password, then try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const fillDemo = (demoRole) => {
    if (demoRole === "agent") {
      setRole("agent");
      setForm({ email: "agent@quickdesk.dev", password: "Agent#Pass1" });
    } else {
      setRole("employee");
      setForm({ email: "employee@quickdesk.dev", password: "Employee#Pass1" });
    }
    setError("");
  };

  return (
    <AuthSplitLayout title="Sign in">
      <div className="auth-tabs" role="tablist" aria-label="Sign in as">
        <div
          className={`auth-tab-pill ${role === "agent" ? "tab-agent" : "tab-employee"}`}
          aria-hidden="true"
        />
        {ROLES.map((item) => (
          <button
            key={item.id}
            ref={(node) => {
              tabRefs.current[item.id] = node;
            }}
            type="button"
            className={`auth-tab ${role === item.id ? "active" : ""}`}
            role="tab"
            id={`login-tab-${item.id}`}
            aria-selected={role === item.id}
            aria-controls="login-panel"
            tabIndex={role === item.id ? 0 : -1}
            onClick={() => moveRole(item.id)}
            onKeyDown={onTabKeyDown}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id="login-panel"
        aria-labelledby={`login-tab-${role}`}
        className="auth-panel"
      >
        <p className="auth-lede">{selected.lede}</p>

        <form onSubmit={submit} className="auth-form" noValidate>
          <div className="form-group">
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              name="email"
              autoComplete="username"
              required
              aria-invalid={error ? true : undefined}
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>

          <PasswordField
            id="login-password"
            value={form.password}
            invalid={Boolean(error)}
            describedBy={error ? "login-error" : undefined}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />

          {error && (
            <div id="login-error" className="form-error" role="alert">
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            className="primary btn-primary"
            disabled={submitting}
            aria-busy={submitting}
          >
            {submitting ? (
              <>
                <Loader2 size={16} className="spinner" style={{ marginRight: "8px" }} />
                Signing in…
              </>
            ) : (
              "Sign in"
            )}
          </button>
        </form>

        <div className="auth-demo-bar">
          <span className="auth-demo-label">Quick fill:</span>
          <button
            type="button"
            className="btn-demo-pill"
            onClick={() => fillDemo("employee")}
          >
            Demo Employee
          </button>
          <button
            type="button"
            className="btn-demo-pill"
            onClick={() => fillDemo("agent")}
          >
            Demo Agent
          </button>
        </div>

        <div className="auth-role-footer">
          {role === "employee" ? (
            <div className="auth-switch">
              <span>New employee? </span>
              <Link to="/register">Create an employee account</Link>
            </div>
          ) : (
            <p className="auth-note">
              Agent accounts are issued by the desk. Creating an account is for employees.
            </p>
          )}
        </div>
      </div>
    </AuthSplitLayout>
  );
}
