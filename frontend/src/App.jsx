import { useState, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./context/AuthContext";
import Dashboard from "./pages/Dashboard";
import NewTicket from "./pages/NewTicket";
import MyTickets from "./pages/MyTickets";
import AgentDashboard from "./pages/AgentDashboard";
import TicketDetail from "./pages/TicketDetail";
import EmployeeTicketDetail from "./pages/EmployeeTicketDetail";
import Metrics from "./pages/Metrics";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Register from "./pages/Register";
import client from "./api/client";

function Protected({ children, role }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading-state">Loading workspace...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to="/" replace />;
  return children;
}

function AgentTicketRedirect() {
  const [target, setTarget] = useState(null);

  useEffect(() => {
    const lastId = sessionStorage.getItem("quickdesk_last_agent_ticket");
    if (lastId) {
      setTarget(`/tickets/${lastId}`);
      return;
    }
    client
      .get("/api/tickets?page_size=1")
      .then(({ data }) => {
        if (data.items && data.items.length > 0) {
          setTarget(`/tickets/${data.items[0].id}`);
        } else {
          setTarget("/dashboard");
        }
      })
      .catch(() => setTarget("/dashboard"));
  }, []);

  if (!target) return <div className="loading-state">Loading ticket...</div>;
  return <Navigate to={target} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route
          path="/tickets/new"
          element={
            <Protected role="employee">
              <NewTicket />
            </Protected>
          }
        />
        <Route
          path="/tickets/mine"
          element={
            <Protected role="employee">
              <MyTickets />
            </Protected>
          }
        />
        <Route
          path="/tickets/mine/:id"
          element={
            <Protected role="employee">
              <EmployeeTicketDetail />
            </Protected>
          }
        />
        <Route
          path="/dashboard"
          element={
            <Protected role="agent">
              <AgentDashboard />
            </Protected>
          }
        />
        <Route
          path="/tickets"
          element={
            <Protected role="agent">
              <AgentTicketRedirect />
            </Protected>
          }
        />
        <Route
          path="/tickets/:id"
          element={
            <Protected role="agent">
              <TicketDetail />
            </Protected>
          }
        />
        <Route
          path="/metrics"
          element={
            <Protected role="agent">
              <Metrics />
            </Protected>
          }
        />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
