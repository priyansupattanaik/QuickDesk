import { createContext, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";
const AuthContext = createContext(null);
// localStorage is XSS-exposed, but avoids CSRF; SameSite=Lax cookies are a future alternative.
// This internal app accepts that tradeoff, with refresh and rotation still a known limitation.

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { if (!localStorage.getItem("quickdesk_token")) return setLoading(false); client.get("/api/auth/me").then(({ data }) => setUser(data)).catch(() => localStorage.removeItem("quickdesk_token")).finally(() => setLoading(false)); }, []);
  const login = async (credentials) => { const { data } = await client.post("/api/auth/login", credentials); localStorage.setItem("quickdesk_token", data.access_token); setUser(data.user); navigate("/"); };
  const logout = () => { localStorage.removeItem("quickdesk_token"); setUser(null); navigate("/login"); };
  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}
export const useAuth = () => useContext(AuthContext);
