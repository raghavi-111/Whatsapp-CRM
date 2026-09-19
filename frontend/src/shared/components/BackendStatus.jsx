import { useEffect, useState } from "react";

import apiClient from "../services/apiClient.js";

function BackendStatus() {
  const [status, setStatus] = useState({
    loading: true,
    connected: false,
    message: "Checking backend connection...",
  });

  useEffect(() => {
    let isMounted = true;

    apiClient
      .get("/health/")
      .then((response) => {
        if (!isMounted) return;
        setStatus({
          loading: false,
          connected: true,
          message: response.data.message,
        });
      })
      .catch(() => {
        if (!isMounted) return;
        setStatus({
          loading: false,
          connected: false,
          message: "Backend is not reachable yet.",
        });
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const className = status.connected ? "status status--ok" : "status status--error";

  return (
    <div className={className} role="status" aria-live="polite">
      <span className="status__dot" />
      <span>{status.loading ? "Checking backend connection..." : status.message}</span>
    </div>
  );
}

export default BackendStatus;
