export function notify(type, title, message = "") {
  window.dispatchEvent(
    new CustomEvent("crm-notification", {
      detail: {
        id: `${Date.now()}-${Math.random()}`,
        type,
        title,
        message,
        createdAt: new Date().toISOString(),
      },
    }),
  );
}
