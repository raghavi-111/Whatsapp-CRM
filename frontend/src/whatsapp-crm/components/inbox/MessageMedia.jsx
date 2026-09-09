/**
 * Message Media
 *
 * Renders WhatsApp media attachments inside Inbox message bubbles.
 * Supports uploaded/local file URLs and Meta-hosted media URLs without
 * changing the surrounding message ordering or WebSocket behavior.
 */
function getMediaUrl(message) {
  return message.media_file_url || message.media_url || "";
}

function MessageMedia({ message }) {
  const url = getMediaUrl(message);
  const label = message.media_filename || message.message_type;

  if (!url) {
    return <p className="media-placeholder">{label}</p>;
  }

  if (message.message_type === "image") {
    return <img alt={message.text || label} className="message-image" src={url} />;
  }

  if (message.message_type === "audio") {
    return <audio className="message-player" controls src={url} />;
  }

  if (message.message_type === "video") {
    return <video className="message-player" controls src={url} />;
  }

  return (
    <a className="media-link" href={url} rel="noreferrer" target="_blank">
      {label}
    </a>
  );
}

export default MessageMedia;
