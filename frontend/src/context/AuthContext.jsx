import { createContext, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { if (!localStorage.getItem("quickdesk_token")) return setLoading(false); client.get("/api/auth/me").then(({ data }) => setUser(data)).catch((error) => { if (error.response?.status === 401) { localStorage.removeItem("quickdesk_token"); navigate("/login", { replace: true }); } }).finally(() => setLoading(false)); }, [navigate]);
  const login = async (credentials, expectedRole) => {
    const { data } = await client.post("/api/auth/login", credentials);
    if (expectedRole && data.user.role !== expectedRole) {
      const error = new Error("role_mismatch");
      error.code = "role_mismatch";
      error.role = data.user.role;
      throw error;
    }
    localStorage.setItem("quickdesk_token", data.access_token);
    setUser(data.user);
    if (data.user.role === "agent") {
      navigate("/dashboard", { replace: true });
    } else {
      navigate("/tickets/mine", { replace: true });
    }
  };
  const logout = () => { localStorage.removeItem("quickdesk_token"); setUser(null); navigate("/login"); };
  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}
export const useAuth = () => useContext(AuthContext);
