import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Inbox,
  Ticket,
  BarChart3,
  PlusSquare,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

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
  }, [location.pathname]);

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
        <div className="mobile-user-avatar" title={user?.email}>
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
            title={collapsed ? "Expand sidebar (QD)" : "QuickDesk"}
          >
            <span className="brand-name-full">QuickDesk</span>
            <span className="brand-name-short">QD</span>
          </div>

          <button
            type="button"
            className="sidebar-toggle-btn"
            onClick={toggleSidebar}
            aria-label={collapsed ? "Expand sidebar" : "Retract sidebar"}
            title={collapsed ? "Expand sidebar" : "Retract sidebar"}
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

          <button
            type="button"
            onClick={logout}
            className="nav-item nav-action"
            data-tooltip="Sign out"
          >
            <LogOut size={18} className="nav-icon" />
            <span className="nav-text">Sign out</span>
          </button>
        </nav>

        <div
          className="rail-user"
          data-tooltip={`${user?.email || "User"} (${user?.role || ""})`}
        >
          <div className="rail-user-avatar" aria-hidden="true">
            {initials}
          </div>
          <div className="rail-user-info">
            <span className="user-email" title={user?.email}>
              {user?.email}
            </span>
            <span className="user-role-badge">{user?.role}</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
