import { useEffect, useMemo, useState } from "react";

import { useNotifications } from "./NotificationProvider.jsx";

function Toast({ notification, onDismiss }) {
  useEffect(() => {
    const timeoutId = window.setTimeout(() => onDismiss(notification.id), 5000);
    return () => window.clearTimeout(timeoutId);
  }, [notification.id, onDismiss]);

  return (
    <div className={`toast toast--${notification.type}`}>
      <div>
        <strong>{notification.title}</strong>
        {notification.message ? <p>{notification.message}</p> : null}
      </div>
      <button aria-label="Dismiss notification" onClick={() => onDismiss(notification.id)} type="button">
        x
      </button>
    </div>
  );
}

function ToastStack() {
  const { notifications, dismissNotification } = useNotifications();
  const recentToasts = useMemo(() => notifications.slice(0, 4), [notifications]);
  const [visibleIds, setVisibleIds] = useState([]);

  useEffect(() => {
    setVisibleIds((current) => {
      const nextIds = recentToasts.map((notification) => notification.id);
      return [...new Set([...nextIds, ...current])].filter((id) => nextIds.includes(id));
    });
  }, [recentToasts]);

  return (
    <div className="toast-stack">
      {recentToasts
        .filter((notification) => visibleIds.includes(notification.id))
        .map((notification) => (
          <Toast key={notification.id} notification={notification} onDismiss={dismissNotification} />
        ))}
    </div>
  );
}

export default ToastStack;
