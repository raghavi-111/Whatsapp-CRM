import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .sending import get_graph_version


logger = logging.getLogger(__name__)
CONNECTION_TEST_TIMEOUT_SECONDS = 15


@dataclass
class WhatsAppConnectionTestError(Exception):
    message: str
    status_code: int


def _meta_error_payload(error):
    try:
        body = error.read().decode("utf-8", errors="replace")
        payload = json.loads(body) if body else {}
    except (json.JSONDecodeError, AttributeError):
        return {}
    meta_error = payload.get("error", {}) if isinstance(payload, dict) else {}
    return meta_error if isinstance(meta_error, dict) else {}


def test_whatsapp_connection(config):
    query = urlencode({"fields": "id,display_phone_number,verified_name"})
    url = f"https://graph.facebook.com/{get_graph_version()}/{config.phone_number_id}?{query}"
    request = Request(
        url,
        headers={"Authorization": f"Bearer {config.access_token}"},
        method="GET",
    )

    try:
        with urlopen(request, timeout=CONNECTION_TEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            payload = json.loads(body) if body else {}
    except HTTPError as error:
        meta_error = _meta_error_payload(error)
        code = meta_error.get("code")
        error_subcode = meta_error.get("error_subcode")
        logger.warning(
            "Meta WhatsApp connection test rejected status=%s code=%s subcode=%s phone_number_id=%s",
            error.code,
            code,
            error_subcode,
            config.phone_number_id,
        )
        if code == 190 or error.code == 401:
            raise WhatsAppConnectionTestError(
                "Meta rejected the access token. Update the Permanent Access Token and try again.", 400
            ) from error
        if error.code == 404 or code == 100:
            raise WhatsAppConnectionTestError(
                "Meta could not find that Phone Number ID. Check the saved Phone Number ID and try again.", 400
            ) from error
        if error.code == 403 or code in {10, 200}:
            raise WhatsAppConnectionTestError(
                "The access token does not have permission to read this WhatsApp phone number.", 400
            ) from error
        raise WhatsAppConnectionTestError("Meta WhatsApp API rejected the connection test.", 502) from error
    except (URLError, TimeoutError) as error:
        logger.warning("Meta WhatsApp connection test unavailable phone_number_id=%s", config.phone_number_id)
        raise WhatsAppConnectionTestError(
            "Meta WhatsApp API is unavailable or timed out. Please try again.", 503
        ) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        logger.warning("Meta WhatsApp connection test returned malformed JSON phone_number_id=%s", config.phone_number_id)
        raise WhatsAppConnectionTestError("Meta WhatsApp API returned an invalid response.", 502) from error

    if not isinstance(payload, dict) or not payload.get("id"):
        logger.warning("Meta WhatsApp connection test response missing id phone_number_id=%s", config.phone_number_id)
        raise WhatsAppConnectionTestError("Meta WhatsApp API returned an invalid response.", 502)

    return {
        "phone_number_id": str(payload["id"]),
        "display_phone_number": str(payload.get("display_phone_number") or ""),
        "verified_name": str(payload.get("verified_name") or ""),
    }
