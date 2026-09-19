import { AUTH_TOKENS_CHANGED_EVENT, getAccessToken } from "../../shared/services/tokenStorage.js";

function getWebSocketUrl() {
  const configuredBaseUrl = import.meta.env.VITE_WS_BASE_URL;
  if (configuredBaseUrl) {
    return `${configuredBaseUrl}/inbox/`;
  }

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
  const url = new URL(apiBaseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/inbox/";
  url.search = "";
  return url.toString();
}

export function connectInboxWebSocket({ onEvent, onStatus }) {
  let socket = null;
  let connectTimer = null;
  let reconnectTimer = null;
  let shouldReconnect = true;

  function clearTimers() {
    if (connectTimer) {
      window.clearTimeout(connectTimer);
      connectTimer = null;
    }
    if (reconnectTimer) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function closeSocket() {
    const currentSocket = socket;
    socket = null;

    if (!currentSocket) return;

    currentSocket.onmessage = null;
    currentSocket.onclose = null;
    currentSocket.onerror = null;

    if (currentSocket.readyState === WebSocket.CONNECTING) {
      currentSocket.onopen = () => currentSocket.close(1000, "Client disconnected");
      return;
    }

    if (currentSocket.readyState === WebSocket.OPEN) {
      currentSocket.close(1000, "Client disconnected");
    }
  }

  function scheduleConnect(delay = 100) {
    if (!shouldReconnect || connectTimer) return;
    connectTimer = window.setTimeout(() => {
      connectTimer = null;
      connect();
    }, delay);
  }

  function connect() {
    if (!shouldReconnect) return;

    const token = getAccessToken();
    if (!token) {
      onStatus?.("disconnected");
      return;
    }

    if (socket && [WebSocket.CONNECTING, WebSocket.OPEN].includes(socket.readyState)) {
      return;
    }

    const url = new URL(getWebSocketUrl());
    url.searchParams.set("token", token);
    socket = new WebSocket(url.toString());
    onStatus?.("connecting");

    socket.onopen = () => onStatus?.("connecting");
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload?.event_type === "connected") {
          onStatus?.("connected");
        }
        onEvent?.(payload);
      } catch {
        // Ignore malformed realtime messages.
      }
    };
    socket.onclose = () => {
      socket = null;
      onStatus?.("disconnected");
      if (shouldReconnect) {
        scheduleConnect(3000);
      }
    };
    socket.onerror = () => {
      onStatus?.("disconnected");
    };
  }

  function reconnectWithLatestToken() {
    if (!shouldReconnect) return;
    clearTimers();
    closeSocket();
    scheduleConnect(0);
  }

  window.addEventListener(AUTH_TOKENS_CHANGED_EVENT, reconnectWithLatestToken);
  scheduleConnect();

  return function disconnect() {
    shouldReconnect = false;
    window.removeEventListener(AUTH_TOKENS_CHANGED_EVENT, reconnectWithLatestToken);
    clearTimers();
    closeSocket();
    onStatus?.("disconnected");
  };
}
