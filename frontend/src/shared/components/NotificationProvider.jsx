import { createContext, useContext, useEffect, useMemo, useState } from "react";

const NotificationContext = createContext({
  notifications: [],
  pushNotification: () => {},
  dismissNotification: () => {},
  clearNotifications: () => {},
});

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([]);

  function pushNotification(notification) {
    const nextNotification = {
      id: notification.id || `${Date.now()}-${Math.random()}`,
      type: notification.type || "info",
      title: notification.title || "Notification",
      message: notification.message || "",
      createdAt: notification.createdAt || new Date().toISOString(),
    };
    setNotifications((current) => [nextNotification, ...current].slice(0, 25));
    return nextNotification.id;
  }

  function dismissNotification(notificationId) {
    setNotifications((current) => current.filter((notification) => notification.id !== notificationId));
  }

  function clearNotifications() {
    setNotifications([]);
  }

  useEffect(() => {
    function handleNotification(event) {
      pushNotification(event.detail || {});
    }

    window.addEventListener("crm-notification", handleNotification);
    return () => window.removeEventListener("crm-notification", handleNotification);
  }, []);

  const value = useMemo(
    () => ({ notifications, pushNotification, dismissNotification, clearNotifications }),
    [notifications],
  );

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}

export function useNotifications() {
  return useContext(NotificationContext);
}
