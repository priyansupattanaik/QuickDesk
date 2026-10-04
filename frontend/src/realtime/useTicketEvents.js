import { useEffect, useRef } from "react";
import client, { apiBase } from "../api/client";

function readEvent(event) {
  try {
    return JSON.parse(event.data);
  } catch {
    return null;
  }
}

export default function useTicketEvents(handlers) {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    let source;
    let retryTimer;
    let retryDelay = 1000;
    let stopped = false;
    const connect = () => {
      const token = localStorage.getItem("quickdesk_token");
      if (!token || stopped) return;
      const base = apiBase.replace(/\/$/, "");
      source = new EventSource(`${base}/api/events?token=${encodeURIComponent(token)}`);
      source.onopen = () => {
        retryDelay = 1000;
        handlersRef.current.onOpen?.();
      };
      source.addEventListener("ticket_created", (event) => {
        const data = readEvent(event);
        if (data) handlersRef.current.onTicketCreated?.(data);
      });
      source.addEventListener("ticket_resolved", (event) => {
        const data = readEvent(event);
        if (data) handlersRef.current.onTicketResolved?.(data);
      });
      source.onerror = () => {
        if (stopped) return;
        source.close();
        client.get("/api/auth/me").catch((error) => {
          if (error.response?.status === 401) {
            localStorage.removeItem("quickdesk_token");
            window.location.assign("/login");
          }
        });
        retryTimer = window.setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 30000);
      };
    };
    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      source?.close();
    };
  }, []);
}
