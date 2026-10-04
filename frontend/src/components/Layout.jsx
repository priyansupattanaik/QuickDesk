import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Inbox, Ticket, BarChart3, PlusSquare, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const isAgent = user?.role === "agent";
  const isEmployee = user?.role === "employee";

  // Check if currently viewing a ticket detail
  const isViewingTicket = location.pathname.startsWith("/tickets/") && !location.pathname.startsWith("/tickets/mine");
  const lastTicketId = sessionStorage.getItem("quickdesk_last_agent_ticket");
  const ticketTarget = isViewingTicket ? location.pathname : (lastTicketId ? `/tickets/${lastTicketId}` : "/tickets");

  return (
    <div className="app-shell">
      <aside className="left-rail">
        <div className="rail-brand">
          <span className="brand-name">QuickDesk</span>
        </div>

        <nav className="rail-nav" aria-label="Main Navigation">
          {isAgent && (
            <>
              <NavLink
                to="/dashboard"
                className={({ isActive }) =>
                  `nav-item ${isActive && !isViewingTicket ? "active" : ""}`
                }
              >
                <Inbox size={18} className="nav-icon" />
                <span className="nav-text">Queue</span>
              </NavLink>
              <NavLink
                to={ticketTarget}
                className={({ isActive }) =>
                  `nav-item ${isViewingTicket || isActive ? "active" : ""}`
                }
              >
                <Ticket size={18} className="nav-icon" />
                <span className="nav-text">Ticket</span>
              </NavLink>
              <NavLink
                to="/metrics"
                className={({ isActive }) =>
                  `nav-item ${isActive ? "active" : ""}`
                }
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
              >
                <Ticket size={18} className="nav-icon" />
                <span className="nav-text">My Tickets</span>
              </NavLink>
              <NavLink
                to="/tickets/new"
                className={({ isActive }) =>
                  `nav-item ${isActive ? "active" : ""}`
                }
              >
                <PlusSquare size={18} className="nav-icon" />
                <span className="nav-text">New ticket</span>
              </NavLink>
            </>
          )}

          <button type="button" onClick={logout} className="nav-item nav-action">
            <LogOut size={18} className="nav-icon" />
            <span className="nav-text">Sign out</span>
          </button>
        </nav>

        <div className="rail-user">
          <div className="user-email" title={user?.email}>{user?.email}</div>
          <span className="user-role">{user?.role}</span>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
