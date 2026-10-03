import { useEffect } from "react";
import client from "../api/client";

export default function useTicketEvents({ onOpen, onTicketCreated, onTicketResolved }) {
  useEffect(() => {
    let source;
    let retryTimer;
    let retryDelay = 1000;
    let stopped = false;
    const connect = () => {
      const token = localStorage.getItem("quickdesk_token");
      if (!token || stopped) return;
      const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
      source = new EventSource(`${apiBase}/api/events?token=${encodeURIComponent(token)}`);
      source.onopen = () => { retryDelay = 1000; onOpen?.(); };
      source.addEventListener("ticket_created", (event) => onTicketCreated?.(JSON.parse(event.data)));
      source.addEventListener("ticket_resolved", (event) => onTicketResolved?.(JSON.parse(event.data)));
      source.onerror = () => {
        source.close();
        client.get("/api/auth/me").catch((error) => {
          if (error.response?.status === 401) {
            localStorage.removeItem("quickdesk_token");
            window.location.assign("/login");
          }
        });
        if (!stopped) { retryTimer = window.setTimeout(connect, retryDelay); retryDelay = Math.min(retryDelay * 2, 30000); }
      };
    };
    connect();
    return () => { stopped = true; window.clearTimeout(retryTimer); source?.close(); };
  }, [onOpen, onTicketCreated, onTicketResolved]);
}
