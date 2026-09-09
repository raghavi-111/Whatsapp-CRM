import re
import unicodedata
from urllib.parse import urlparse


def normalized_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return f"+{digits}" if 7 <= len(digits) <= 15 else ""


def normalized_domain(value):
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    parsed = urlparse(candidate if "://" in candidate else f"//{candidate}")
    domain = (parsed.hostname or "").casefold().rstrip(".")
    return domain[4:] if domain.startswith("www.") else domain


def normalized_text(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", value).split())


def confirmed_whatsapp(business):
    for contact in business.get("whatsapp_contacts") or []:
        if isinstance(contact, dict) and contact.get("status") == "CONFIRMED_PUBLIC":
            number = normalized_phone(contact.get("normalized") or contact.get("number"))
            if number:
                return number
    return ""


def provider_place_id(business):
    for field in ("place_id", "google_place_id", "provider_place_id", "osm_id"):
        if business.get(field):
            return f"{business.get('source', '')}:{business[field]}"[:255]
    return ""


def business_identity(business):
    place_id = provider_place_id(business)
    if place_id:
        return f"place:{place_id}"
    domain = normalized_domain(business.get("website"))
    if domain:
        return f"domain:{domain}"
    name = normalized_text(business.get("name"))
    address = normalized_text(business.get("address"))
    if name and address:
        return f"name-address:{name}|{address}"
    latitude, longitude = business.get("latitude"), business.get("longitude")
    if name and latitude is not None and longitude is not None:
        return f"name-coordinates:{name}|{float(latitude):.5f}|{float(longitude):.5f}"
    phone = normalized_phone(business.get("phone"))
    return f"phone:{phone}" if phone else f"name:{name}"
