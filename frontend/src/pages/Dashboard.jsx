import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Dashboard() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="loading-state">Loading workspace...</div>;
  }

  if (user?.role === "agent") {
    return <Navigate to="/dashboard" replace />;
  }

  if (user?.role === "employee") {
    return <Navigate to="/tickets/mine" replace />;
  }

  return <Navigate to="/login" replace />;
}

