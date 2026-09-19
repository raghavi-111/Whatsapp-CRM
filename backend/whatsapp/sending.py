import json
import logging
import mimetypes
import os
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)
_forced_send_mode = ContextVar("forced_whatsapp_send_mode", default=None)


class WhatsAppSendError(Exception):
    pass


@dataclass
class WhatsAppSendResult:
    external_message_id: str
    raw_response: dict
    meta_media_id: str = ""


def normalize_phone_number(value):
    """Return the international digits Meta expects without changing stored data."""
    normalized = "".join(character for character in str(value or "") if character.isdigit())
    if not normalized:
        raise WhatsAppSendError("Contact phone number is missing or invalid.")
    return normalized


def meta_http_error(error, operation):
    """Log Meta's safe structured error fields and return a useful client error."""
    raw_body = error.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        payload = {}
    meta_error = payload.get("error") if isinstance(payload, dict) else {}
    meta_error = meta_error if isinstance(meta_error, dict) else {}
    fields = {
        "message": meta_error.get("message"),
        "type": meta_error.get("type"),
        "code": meta_error.get("code"),
        "error_subcode": meta_error.get("error_subcode"),
        "fbtrace_id": meta_error.get("fbtrace_id"),
        "error_data": meta_error.get("error_data"),
    }
    logger.warning("Meta WhatsApp %s failed status=%s error=%s", operation, error.code, fields)
    if fields["code"] == 190:
        return WhatsAppSendError("Message failed: WhatsApp authentication failed. Update the permanent access token in Settings.")
    if fields["code"] == 131047:
        return WhatsAppSendError("Message failed: recipient is outside the 24-hour window. Send an approved template.")
    safe_message = str(fields["message"] or "").strip()
    if safe_message:
        return WhatsAppSendError(f"Message failed: {safe_message}")
    return WhatsAppSendError(f"Meta WhatsApp API rejected the {operation} (HTTP {error.code}).")


def get_send_mode():
    return _forced_send_mode.get() or os.environ.get("WHATSAPP_SEND_MODE", "mock").lower()


@contextmanager
def force_whatsapp_send_mode(mode):
    token = _forced_send_mode.set(mode)
    try:
        yield
    finally:
        _forced_send_mode.reset(token)


def get_graph_version():
    return os.environ.get("META_GRAPH_API_VERSION", "v21.0")


def build_graph_request(url, payload):
    return Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )


def send_whatsapp_text_message(config, to_phone_number, text):
    to_phone_number = normalize_phone_number(to_phone_number)
    if not text.strip():
        raise WhatsAppSendError("Message text is required.")

    if get_send_mode() == "mock":
        external_message_id = f"mock-wamid-{uuid.uuid4()}"
        logger.info(
            "Mock WhatsApp send succeeded phone_number_id=%s external_message_id=%s",
            getattr(config, "phone_number_id", "mock"),
            external_message_id,
        )
        return WhatsAppSendResult(
            external_message_id=external_message_id,
            raw_response={"messages": [{"id": external_message_id}]},
        )

    if get_send_mode() != "real":
        raise WhatsAppSendError("Invalid WHATSAPP_SEND_MODE. Use mock or real.")

    if not config:
        raise WhatsAppSendError("Missing active WhatsApp configuration.")
    if not config.phone_number_id:
        raise WhatsAppSendError("WhatsApp phone number ID is missing.")
    if not config.access_token:
        raise WhatsAppSendError("WhatsApp access token is missing.")

    url = f"https://graph.facebook.com/{get_graph_version()}/{config.phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone_number,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            response_body = response.read().decode("utf-8")
            response_data = json.loads(response_body) if response_body else {}
    except HTTPError as error:
        raise meta_http_error(error, "message send") from error
    except URLError as error:
        logger.warning(
            "Meta WhatsApp send network failure phone_number_id=%s reason=%s",
            config.phone_number_id,
            error.reason,
        )
        raise WhatsAppSendError("Network error while sending WhatsApp message.") from error
    except TimeoutError as error:
        logger.warning("Meta WhatsApp send timed out phone_number_id=%s", config.phone_number_id)
        raise WhatsAppSendError("Timed out while sending WhatsApp message.") from error
    except json.JSONDecodeError as error:
        logger.warning("Meta WhatsApp send returned invalid JSON phone_number_id=%s", config.phone_number_id)
        raise WhatsAppSendError("Meta WhatsApp API returned an invalid response.") from error

    messages = response_data.get("messages", [])
    external_message_id = messages[0].get("id", "") if messages else ""
    if not external_message_id:
        logger.warning("Meta WhatsApp send response missing message id phone_number_id=%s", config.phone_number_id)

    logger.info(
        "Meta WhatsApp send succeeded phone_number_id=%s external_message_id=%s",
        config.phone_number_id,
        external_message_id,
    )
    return WhatsAppSendResult(external_message_id=external_message_id, raw_response=response_data)


def send_whatsapp_template_message(config, to_phone_number, template_name, language, parameters=None):
    if not to_phone_number:
        raise WhatsAppSendError("Contact phone number is missing.")
    if not template_name:
        raise WhatsAppSendError("Template name is missing.")
    if not language:
        raise WhatsAppSendError("Template language is missing.")

    if get_send_mode() == "mock":
        external_message_id = f"mock-wamid-{uuid.uuid4()}"
        logger.info(
            "Mock WhatsApp template send succeeded phone_number_id=%s template=%s external_message_id=%s",
            getattr(config, "phone_number_id", "mock"),
            template_name,
            external_message_id,
        )
        return WhatsAppSendResult(
            external_message_id=external_message_id,
            raw_response={"messages": [{"id": external_message_id}]},
        )

    if get_send_mode() != "real":
        raise WhatsAppSendError("Invalid WHATSAPP_SEND_MODE. Use mock or real.")

    if not config:
        raise WhatsAppSendError("Missing active WhatsApp configuration.")
    if not config.phone_number_id:
        raise WhatsAppSendError("WhatsApp phone number ID is missing.")
    if not config.access_token:
        raise WhatsAppSendError("WhatsApp access token is missing.")

    parameter_values = parameters or []
    components = []
    if parameter_values:
        components.append(
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(parameter)}
                    for parameter in parameter_values
                ],
            }
        )

    template_payload = {
        "name": template_name,
        "language": {"code": language},
    }
    if components:
        template_payload["components"] = components

    url = f"https://graph.facebook.com/{get_graph_version()}/{config.phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "type": "template",
        "template": template_payload,
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            response_body = response.read().decode("utf-8")
            response_data = json.loads(response_body) if response_body else {}
    except HTTPError as error:
        safe_body = error.read().decode("utf-8", errors="replace")
        logger.warning(
            "Meta WhatsApp template send failed status=%s phone_number_id=%s template=%s response=%s",
            error.code,
            config.phone_number_id,
            template_name,
            safe_body[:500],
        )
        raise WhatsAppSendError("Meta WhatsApp API rejected the template message.") from error
    except URLError as error:
        logger.warning(
            "Meta WhatsApp template send network failure phone_number_id=%s template=%s reason=%s",
            config.phone_number_id,
            template_name,
            error.reason,
        )
        raise WhatsAppSendError("Network error while sending WhatsApp template message.") from error
    except TimeoutError as error:
        logger.warning(
            "Meta WhatsApp template send timed out phone_number_id=%s template=%s",
            config.phone_number_id,
            template_name,
        )
        raise WhatsAppSendError("Timed out while sending WhatsApp template message.") from error
    except json.JSONDecodeError as error:
        logger.warning(
            "Meta WhatsApp template send returned invalid JSON phone_number_id=%s template=%s",
            config.phone_number_id,
            template_name,
        )
        raise WhatsAppSendError("Meta WhatsApp API returned an invalid response.") from error

    messages = response_data.get("messages", [])
    external_message_id = messages[0].get("id", "") if messages else ""
    if not external_message_id:
        logger.warning(
            "Meta WhatsApp template send response missing message id phone_number_id=%s template=%s",
            config.phone_number_id,
            template_name,
        )

    logger.info(
        "Meta WhatsApp template send succeeded phone_number_id=%s template=%s external_message_id=%s",
        config.phone_number_id,
        template_name,
        external_message_id,
    )
    return WhatsAppSendResult(external_message_id=external_message_id, raw_response=response_data)


def upload_whatsapp_media(config, media_file, mime_type):
    if not media_file:
        raise WhatsAppSendError("Media file is required.")

    if get_send_mode() == "mock":
        meta_media_id = f"mock-media-{uuid.uuid4()}"
        logger.info(
            "Mock WhatsApp media upload succeeded phone_number_id=%s media_id=%s",
            getattr(config, "phone_number_id", "mock"),
            meta_media_id,
        )
        return meta_media_id, {"id": meta_media_id}

    if get_send_mode() != "real":
        raise WhatsAppSendError("Invalid WHATSAPP_SEND_MODE. Use mock or real.")

    if not config:
        raise WhatsAppSendError("Missing active WhatsApp configuration.")
    if not config.phone_number_id:
        raise WhatsAppSendError("WhatsApp phone number ID is missing.")
    if not config.access_token:
        raise WhatsAppSendError("WhatsApp access token is missing.")

    file_name = getattr(media_file, "name", "upload")
    content_type = mime_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    file_bytes = media_file.read()
    try:
        media_file.seek(0)
    except (AttributeError, OSError):
        pass

    boundary = f"----whatsappcrm{uuid.uuid4().hex}"
    parts = [
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="messaging_product"\r\n\r\n'
            "whatsapp\r\n"
        ).encode("utf-8"),
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(file_name)}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8"),
        file_bytes,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    body = b"".join(parts)

    url = f"https://graph.facebook.com/{get_graph_version()}/{config.phone_number_id}/media"
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {config.access_token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            response_data = json.loads(response_body) if response_body else {}
    except HTTPError as error:
        raise meta_http_error(error, "media upload") from error
    except URLError as error:
        logger.warning(
            "Meta WhatsApp media upload network failure phone_number_id=%s reason=%s",
            config.phone_number_id,
            error.reason,
        )
        raise WhatsAppSendError("Network error while uploading WhatsApp media.") from error
    except TimeoutError as error:
        logger.warning("Meta WhatsApp media upload timed out phone_number_id=%s", config.phone_number_id)
        raise WhatsAppSendError("Timed out while uploading WhatsApp media.") from error
    except json.JSONDecodeError as error:
        logger.warning("Meta WhatsApp media upload returned invalid JSON phone_number_id=%s", config.phone_number_id)
        raise WhatsAppSendError("Meta WhatsApp API returned an invalid media upload response.") from error

    meta_media_id = response_data.get("id", "")
    if not meta_media_id:
        raise WhatsAppSendError("Meta WhatsApp media upload response missing media ID.")

    logger.info(
        "Meta WhatsApp media upload succeeded phone_number_id=%s media_id=%s",
        config.phone_number_id,
        meta_media_id,
    )
    return meta_media_id, response_data


def send_whatsapp_media_message(config, to_phone_number, message_type, meta_media_id="", caption="", filename="", media_url=""):
    to_phone_number = normalize_phone_number(to_phone_number)
    if message_type not in {"image", "document", "audio", "video"}:
        raise WhatsAppSendError("Unsupported media message type.")
    if not meta_media_id and not media_url:
        raise WhatsAppSendError("A Meta media ID or public media URL is required.")
    if media_url and not media_url.lower().startswith("https://"):
        raise WhatsAppSendError("Media URL must be a public HTTPS URL.")

    if get_send_mode() == "mock":
        external_message_id = f"mock-wamid-{uuid.uuid4()}"
        logger.info(
            "Mock WhatsApp media send succeeded phone_number_id=%s media_id=%s external_message_id=%s",
            getattr(config, "phone_number_id", "mock"),
            meta_media_id or media_url,
            external_message_id,
        )
        return WhatsAppSendResult(
            external_message_id=external_message_id,
            raw_response={"messages": [{"id": external_message_id}]},
            meta_media_id=meta_media_id,
        )

    if get_send_mode() != "real":
        raise WhatsAppSendError("Invalid WHATSAPP_SEND_MODE. Use mock or real.")

    if not config:
        raise WhatsAppSendError("Missing active WhatsApp configuration.")
    if not config.phone_number_id:
        raise WhatsAppSendError("WhatsApp phone number ID is missing.")
    if not config.access_token:
        raise WhatsAppSendError("WhatsApp access token is missing.")

    media_payload = {"id": meta_media_id} if meta_media_id else {"link": media_url}
    if caption and message_type in {"image", "document", "video"}:
        media_payload["caption"] = caption
    if filename and message_type == "document":
        media_payload["filename"] = filename

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone_number,
        "type": message_type,
        message_type: media_payload,
    }

    url = f"https://graph.facebook.com/{get_graph_version()}/{config.phone_number_id}/messages"
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            response_body = response.read().decode("utf-8")
            response_data = json.loads(response_body) if response_body else {}
    except HTTPError as error:
        raise meta_http_error(error, "media message send") from error
    except URLError as error:
        logger.warning(
            "Meta WhatsApp media send network failure phone_number_id=%s media_type=%s reason=%s",
            config.phone_number_id,
            message_type,
            error.reason,
        )
        raise WhatsAppSendError("Network error while sending WhatsApp media.") from error
    except TimeoutError as error:
        logger.warning("Meta WhatsApp media send timed out phone_number_id=%s", config.phone_number_id)
        raise WhatsAppSendError("Timed out while sending WhatsApp media.") from error
    except json.JSONDecodeError as error:
        logger.warning("Meta WhatsApp media send returned invalid JSON phone_number_id=%s", config.phone_number_id)
        raise WhatsAppSendError("Meta WhatsApp API returned an invalid media send response.") from error

    messages = response_data.get("messages", [])
    external_message_id = messages[0].get("id", "") if messages else ""
    if not external_message_id:
        logger.warning("Meta WhatsApp media send response missing message id phone_number_id=%s", config.phone_number_id)

    logger.info(
        "Meta WhatsApp media send succeeded phone_number_id=%s media_type=%s external_message_id=%s",
        config.phone_number_id,
        message_type,
        external_message_id,
    )
    return WhatsAppSendResult(
        external_message_id=external_message_id,
        raw_response=response_data,
        meta_media_id=meta_media_id,
    )


def send_image(config, to_phone_number, *, media_id="", file_url="", caption=""):
    return send_whatsapp_media_message(config, to_phone_number, "image", media_id, caption=caption, media_url=file_url)


def send_document(config, to_phone_number, *, media_id="", file_url="", filename="", caption=""):
    return send_whatsapp_media_message(config, to_phone_number, "document", media_id, caption=caption, filename=filename, media_url=file_url)


def send_video(config, to_phone_number, *, media_id="", file_url="", caption=""):
    return send_whatsapp_media_message(config, to_phone_number, "video", media_id, caption=caption, media_url=file_url)


def send_audio(config, to_phone_number, *, media_id="", file_url=""):
    return send_whatsapp_media_message(config, to_phone_number, "audio", media_id, media_url=file_url)
