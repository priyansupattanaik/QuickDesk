import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
export default function Layout() { const { user, logout } = useAuth(); return <div className="app-shell"><aside><div className="wordmark">QuickDesk<span>.</span></div><nav><NavLink to="/">Overview</NavLink>{user?.role === "agent" && <NavLink to="/agent">Agent space</NavLink>}</nav><div className="account"><strong>{user?.email}</strong><span className="role">{user?.role}</span><button onClick={logout}>Log out</button></div></aside><main><Outlet /></main></div>; }
