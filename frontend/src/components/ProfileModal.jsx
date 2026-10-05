import { useEffect } from "react";
import { X, User, Mail, Shield, KeyRound, CheckCircle2 } from "lucide-react";

function getInitials(user) {
  if (user?.full_name?.trim()) {
    const parts = user.full_name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return parts[0].slice(0, 2).toUpperCase();
  }
  if (user?.email) {
    const namePart = user.email.split("@")[0].replace(/[^a-zA-Z0-9]/g, "");
    return (namePart.slice(0, 2) || user.role?.slice(0, 2) || "QD").toUpperCase();
  }
  return "QD";
}

export default function ProfileModal({ isOpen, onClose, user, onChangePasswordClick }) {
  useEffect(() => {
    if (!isOpen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const initials = getInitials(user);

  return (
    <div
      className="qd-modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="profile-modal-title"
    >
      <div className="qd-modal-container qd-modal-profile">
        <div className="qd-modal-header">
          <div className="qd-modal-header-icon-wrap">
            <User size={20} className="qd-modal-header-icon" />
          </div>
          <div className="qd-modal-header-text">
            <h2 id="profile-modal-title" className="qd-modal-title">
              Employee Profile
            </h2>
            <p className="qd-modal-subtitle">
              Account identity, credentials, and access role details.
            </p>
          </div>
          <button
            type="button"
            className="qd-modal-close-btn"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <X size={18} />
          </button>
        </div>

        <div className="qd-profile-hero">
          <div className="qd-profile-hero-avatar">
            {initials}
          </div>
          <div className="qd-profile-hero-info">
            <div className="qd-profile-hero-name">
              {user?.full_name || "Employee"}
            </div>
            <div className="qd-profile-hero-role-wrapper">
              <span className="qd-profile-hero-role-badge">
                {user?.role || "employee"}
              </span>
              <span className="qd-profile-status-indicator">
                <span className="qd-status-dot" /> Active
              </span>
            </div>
          </div>
        </div>

        <div className="qd-profile-details-card">
          <div className="qd-profile-field-row">
            <div className="qd-profile-field-icon-wrap">
              <User size={16} />
            </div>
            <div className="qd-profile-field-content">
              <span className="qd-profile-field-label">Full Name</span>
              <span className="qd-profile-field-value">{user?.full_name || "—"}</span>
            </div>
          </div>

          <div className="qd-profile-field-divider" />

          <div className="qd-profile-field-row">
            <div className="qd-profile-field-icon-wrap">
              <Mail size={16} />
            </div>
            <div className="qd-profile-field-content">
              <span className="qd-profile-field-label">Email Address</span>
              <span className="qd-profile-field-value">{user?.email || "—"}</span>
            </div>
          </div>

          <div className="qd-profile-field-divider" />

          <div className="qd-profile-field-row">
            <div className="qd-profile-field-icon-wrap">
              <Shield size={16} />
            </div>
            <div className="qd-profile-field-content">
              <span className="qd-profile-field-label">Account Role</span>
              <span className="qd-profile-field-value qd-text-capitalize">
                {user?.role || "employee"}
              </span>
            </div>
          </div>

          <div className="qd-profile-field-divider" />

          <div className="qd-profile-field-row">
            <div className="qd-profile-field-icon-wrap">
              <CheckCircle2 size={16} />
            </div>
            <div className="qd-profile-field-content">
              <span className="qd-profile-field-label">Account Status</span>
              <span className="qd-profile-field-value qd-text-active">Verified & Active</span>
            </div>
          </div>
        </div>

        <div className="qd-profile-security-card">
          <div className="qd-security-info">
            <div className="qd-security-icon-wrap">
              <KeyRound size={18} />
            </div>
            <div className="qd-security-text">
              <span className="qd-security-title">Password & Credentials</span>
              <span className="qd-security-desc">
                Update your account password to maintain security.
              </span>
            </div>
          </div>
          <button
            type="button"
            className="qd-change-password-trigger-btn"
            onClick={() => {
              onClose();
              onChangePasswordClick();
            }}
          >
            <KeyRound size={15} />
            <span>Change Password</span>
          </button>
        </div>

        <div className="qd-modal-actions">
          <button
            type="button"
            className="qd-modal-btn qd-modal-btn-secondary"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
