import { useEffect, useState, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Inbox,
  Ticket,
  BarChart3,
  PlusSquare,
  LogOut,
  User,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Menu,
  X,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import ProfileModal from "./ProfileModal";
import ChangePasswordModal from "./ChangePasswordModal";

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

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem("quickdesk_sidebar_collapsed") === "true";
    } catch {
      return false;
    }
  });

  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [changePasswordModalOpen, setChangePasswordModalOpen] = useState(false);

  const profileContainerRef = useRef(null);

  const isAgent = user?.role === "agent";
  const isEmployee = user?.role === "employee";

  const isViewingTicket =
    location.pathname.startsWith("/tickets/") &&
    !location.pathname.startsWith("/tickets/mine");
  const lastTicketId = sessionStorage.getItem("quickdesk_last_agent_ticket");
  const ticketTarget = isViewingTicket
    ? location.pathname
    : lastTicketId
    ? `/tickets/${lastTicketId}`
    : "/tickets";

  const toggleSidebar = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("quickdesk_sidebar_collapsed", String(next));
      } catch {}
      return next;
    });
  };

  useEffect(() => {
    setMobileOpen(false);
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const handleOutsideClick = (e) => {
      if (profileContainerRef.current && !profileContainerRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    const handleEsc = (e) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleEsc);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleEsc);
    };
  }, [menuOpen]);

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === "Escape" && mobileOpen) {
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mobileOpen]);

  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  const initials = getInitials(user);

  return (
    <div className="app-shell">
      <header className="mobile-header">
        <button
          type="button"
          className="mobile-menu-btn"
          onClick={() => setMobileOpen(true)}
          aria-label="Open navigation menu"
        >
          <Menu size={20} />
        </button>
        <div className="mobile-brand">
          <span className="brand-name">QuickDesk</span>
        </div>
        <div
          className="mobile-user-avatar"
          title={user?.full_name || user?.email}
          onClick={() => setProfileModalOpen(true)}
          role="button"
          tabIndex={0}
          aria-label="Open employee profile"
        >
          {initials}
        </div>
      </header>

      {mobileOpen && (
        <div
          className="mobile-overlay"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={`left-rail ${collapsed ? "collapsed" : ""} ${
          mobileOpen ? "mobile-open" : ""
        }`}
        aria-label="Main Navigation Sidebar"
      >
        <div className="rail-brand">
          <div
            className="brand-display"
            onClick={() => {
              if (collapsed) toggleSidebar();
            }}
            title={collapsed ? "Expand sidebar" : "QuickDesk"}
            data-tooltip={collapsed ? "Expand sidebar" : undefined}
            role={collapsed ? "button" : undefined}
            tabIndex={collapsed ? 0 : undefined}
            aria-label={collapsed ? "QuickDesk — Click to expand sidebar" : "QuickDesk"}
            onKeyDown={(e) => {
              if (collapsed && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                toggleSidebar();
              }
            }}
          >
            <span className="brand-wordmark" aria-label={collapsed ? "QD" : "QuickDesk"}>
              <span className="brand-char brand-char-q">Q</span>
              <span className="brand-chars-uick">uick</span>
              <span className="brand-char brand-char-d">D</span>
              <span className="brand-chars-esk">esk</span>
            </span>
          </div>

          <button
            type="button"
            className="sidebar-toggle-btn"
            onClick={toggleSidebar}
            aria-label={collapsed ? "Expand sidebar" : "Retract sidebar"}
            title={collapsed ? "Expand sidebar" : "Retract sidebar"}
            tabIndex={collapsed ? -1 : 0}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>

          <button
            type="button"
            className="mobile-close-btn"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="rail-nav" aria-label="Main Navigation">
          {isAgent && (
            <>
              <NavLink
                to="/dashboard"
                className={({ isActive }) =>
                  `nav-item ${isActive && !isViewingTicket ? "active" : ""}`
                }
                data-tooltip="Queue"
              >
                <Inbox size={18} className="nav-icon" />
                <span className="nav-text">Queue</span>
              </NavLink>
              <NavLink
                to={ticketTarget}
                className={({ isActive }) =>
                  `nav-item ${isViewingTicket || isActive ? "active" : ""}`
                }
                data-tooltip="Ticket"
              >
                <Ticket size={18} className="nav-icon" />
                <span className="nav-text">Ticket</span>
              </NavLink>
              <NavLink
                to="/metrics"
                className={({ isActive }) =>
                  `nav-item ${isActive ? "active" : ""}`
                }
                data-tooltip="Metrics"
              >
                <BarChart3 size={18} className="nav-icon" />
                <span className="nav-text">Metrics</span>
              </NavLink>
            </>
          )}

          {isEmployee && (
            <>
              <NavLink
                to="/tickets/mine"
                className={({ isActive }) =>
                  `nav-item ${isActive ? "active" : ""}`
                }
                data-tooltip="My Tickets"
              >
                <Ticket size={18} className="nav-icon" />
                <span className="nav-text">My Tickets</span>
              </NavLink>
              <NavLink
                to="/tickets/new"
                className={({ isActive }) =>
                  `nav-item ${isActive ? "active" : ""}`
                }
                data-tooltip="New ticket"
              >
                <PlusSquare size={18} className="nav-icon" />
                <span className="nav-text">New ticket</span>
              </NavLink>
            </>
          )}
        </nav>

        <div className="rail-user-container" ref={profileContainerRef}>
          {menuOpen && (
            <div
              className={`rail-profile-popover ${collapsed ? "popover-collapsed" : ""}`}
              role="menu"
              aria-label="User account menu"
            >
              <div className="profile-popover-header">
                <div className="profile-popover-avatar">{initials}</div>
                <div className="profile-popover-user-meta">
                  <span className="profile-popover-name" title={user?.full_name || "User"}>
                    {user?.full_name || "User"}
                  </span>
                  <span className="profile-popover-email" title={user?.email}>
                    {user?.email}
                  </span>
                </div>
              </div>

              <div className="profile-popover-divider" />

              <button
                type="button"
                className="profile-popover-item"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  setProfileModalOpen(true);
                }}
              >
                <User size={16} className="profile-popover-icon" />
                <span className="profile-popover-text">Profile</span>
              </button>

              <button
                type="button"
                className="profile-popover-item profile-popover-item-signout"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  logout();
                }}
              >
                <LogOut size={16} className="profile-popover-icon" />
                <span className="profile-popover-text">Sign out</span>
              </button>
            </div>
          )}

          <div
            className={`rail-user ${menuOpen ? "menu-open" : ""}`}
            onClick={() => setMenuOpen((prev) => !prev)}
            role="button"
            tabIndex={0}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-label={`User menu for ${user?.full_name || "User"}`}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setMenuOpen((prev) => !prev);
              }
            }}
            data-tooltip={collapsed && !menuOpen ? `${user?.full_name || "User"} (${user?.role || ""})` : undefined}
          >
            <div className="rail-user-avatar" aria-hidden="true">
              {initials}
            </div>
            <div className="rail-user-info">
              <span className="user-name" title={user?.full_name || "User"}>
                {user?.full_name || "User"}
              </span>
              <span className="user-role-badge">{user?.role}</span>
            </div>
            <div className="rail-user-chevron" aria-hidden="true">
              <ChevronUp size={14} className={`profile-chevron ${menuOpen ? "open" : ""}`} />
            </div>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>

      <ProfileModal
        isOpen={profileModalOpen}
        onClose={() => setProfileModalOpen(false)}
        user={user}
        onChangePasswordClick={() => setChangePasswordModalOpen(true)}
      />

      <ChangePasswordModal
        isOpen={changePasswordModalOpen}
        onClose={() => setChangePasswordModalOpen(false)}
      />
    </div>
  );
}
