import { useState, useEffect, useRef } from "react";
import { X, Lock, KeyRound, Eye, EyeOff, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import client from "../api/client";

export default function ChangePasswordModal({ isOpen, onClose }) {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const oldPasswordInputRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  useEffect(() => {
    if (isOpen) {
      const prevOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowOld(false);
      setShowNew(false);
      setShowConfirm(false);
      setError("");
      setSuccess(false);
      setLoading(false);
      setTimeout(() => {
        oldPasswordInputRef.current?.focus();
      }, 50);

      const handleKeyDown = (e) => {
        if (e.key === "Escape" && !loading) {
          onClose();
        }
      };
      window.addEventListener("keydown", handleKeyDown);

      return () => {
        document.body.style.overflow = prevOverflow;
        window.removeEventListener("keydown", handleKeyDown);
      };
    }
  }, [isOpen, loading, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!oldPassword) {
      setError("Please enter your current password.");
      return;
    }
    if (!newPassword) {
      setError("Please enter a new password.");
      return;
    }
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match. Please verify.");
      return;
    }
    if (newPassword === oldPassword) {
      setError("New password must be different from your current password.");
      return;
    }

    setLoading(true);
    try {
      await client.post("/api/auth/change-password", {
        old_password: oldPassword,
        new_password: newPassword,
      });
      setSuccess(true);
      timerRef.current = setTimeout(() => {
        onClose();
      }, 1400);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail) && detail[0]?.msg) {
        setError(detail[0].msg);
      } else {
        setError("Failed to change password. Please verify your current password.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="qd-modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget && !loading) {
          onClose();
        }
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="change-password-title"
    >
      <div className="qd-modal-container qd-modal-change-password">
        <div className="qd-modal-header">
          <div className="qd-modal-header-icon-wrap">
            <KeyRound size={20} className="qd-modal-header-icon" />
          </div>
          <div className="qd-modal-header-text">
            <h2 id="change-password-title" className="qd-modal-title">
              Change Password
            </h2>
            <p className="qd-modal-subtitle">
              Enter your old password and choose a new secure password.
            </p>
          </div>
          <button
            type="button"
            className="qd-modal-close-btn"
            onClick={onClose}
            aria-label="Close dialog"
            disabled={loading}
          >
            <X size={18} />
          </button>
        </div>

        {error && (
          <div className="qd-modal-alert qd-modal-alert-error" role="alert">
            <AlertCircle size={16} className="qd-modal-alert-icon" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="qd-modal-alert qd-modal-alert-success" role="alert">
            <CheckCircle2 size={16} className="qd-modal-alert-icon" />
            <span>Password updated successfully! Closing...</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="qd-modal-form">
          <div className="qd-form-group">
            <label htmlFor="old-password-input" className="qd-form-label">
              Old Password
            </label>
            <div className="qd-password-input-wrapper">
              <input
                id="old-password-input"
                ref={oldPasswordInputRef}
                type={showOld ? "text" : "password"}
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                placeholder="Enter old password"
                className="qd-form-input"
                autoComplete="current-password"
                disabled={loading || success}
                required
              />
              <button
                type="button"
                className="qd-password-toggle-btn"
                onClick={() => setShowOld((prev) => !prev)}
                tabIndex={-1}
                aria-label={showOld ? "Hide current password" : "Show current password"}
              >
                {showOld ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="qd-form-group">
            <label htmlFor="new-password-input" className="qd-form-label">
              New Password
            </label>
            <div className="qd-password-input-wrapper">
              <input
                id="new-password-input"
                type={showNew ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                className="qd-form-input"
                autoComplete="new-password"
                disabled={loading || success}
                required
              />
              <button
                type="button"
                className="qd-password-toggle-btn"
                onClick={() => setShowNew((prev) => !prev)}
                tabIndex={-1}
                aria-label={showNew ? "Hide new password" : "Show new password"}
              >
                {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <span className="qd-form-hint">Must contain at least 8 characters.</span>
          </div>

          <div className="qd-form-group">
            <label htmlFor="confirm-password-input" className="qd-form-label">
              Confirm New Password
            </label>
            <div className="qd-password-input-wrapper">
              <input
                id="confirm-password-input"
                type={showConfirm ? "text" : "password"}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter new password"
                className="qd-form-input"
                autoComplete="new-password"
                disabled={loading || success}
                required
              />
              <button
                type="button"
                className="qd-password-toggle-btn"
                onClick={() => setShowConfirm((prev) => !prev)}
                tabIndex={-1}
                aria-label={showConfirm ? "Hide confirm password" : "Show confirm password"}
              >
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="qd-modal-actions">
            <button
              type="button"
              className="qd-modal-btn qd-modal-btn-secondary"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="qd-modal-btn qd-modal-btn-primary"
              disabled={loading || success}
            >
              {loading ? (
                <>
                  <Loader2 size={16} className="qd-btn-spinner" />
                  <span>Updating...</span>
                </>
              ) : (
                <>
                  <Lock size={15} />
                  <span>Change Password</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
