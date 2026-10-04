import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AuthSplitLayout, PasswordField } from "./Login";
import { Loader2 } from "lucide-react";
import client from "../api/client";

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", full_name: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (form.password.length < 8) {
      return setError("Password must be at least 8 characters");
    }
    setError("");
    setSubmitting(true);
    try {
      await client.post("/api/auth/register", form);
      navigate("/login");
    } catch (e) {
      setError(e.response?.data?.detail || "Unable to create account");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthSplitLayout title="Create an employee account">
      <p className="auth-lede">This form is for employees. Agent accounts are issued by the desk.</p>
      <form onSubmit={submit} className="auth-form" noValidate>
        <div className="form-group">
          <label htmlFor="reg-name">Full name</label>
          <input
            id="reg-name"
            name="name"
            autoComplete="name"
            required
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label htmlFor="reg-email">Email</label>
          <input
            id="reg-email"
            type="email"
            name="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </div>
        <PasswordField
          id="reg-password"
          label="Password (min 8 characters)"
          value={form.password}
          minLength={8}
          autoComplete="new-password"
          invalid={Boolean(error)}
          describedBy={error ? "reg-error" : undefined}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
        {error && (
          <div id="reg-error" className="form-error" role="alert">
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
              Creating account…
            </>
          ) : (
            "Create account"
          )}
        </button>
      </form>
      <div className="auth-switch">
        <span>Already registered? </span>
        <Link to="/login">Sign in</Link>
      </div>
    </AuthSplitLayout>
  );
}
