import logging
import hashlib
import hmac
from datetime import datetime, timezone as datetime_timezone

from django.db import transaction
from django.utils import timezone

from contacts.models import Contact
from conversations.models import Conversation, Message
from realtime.utils import broadcast_inbox_event
from automations.models import AutomationRule
from automations.services import run_automations_on_commit
from pipelines.services import create_lead_deal_for_contact
from broadcasts.services import update_recipient_from_webhook

from .models import WhatsAppBusinessConfig


logger = logging.getLogger(__name__)
SUPPORTED_INBOUND_MESSAGE_TYPES = {
    Message.TYPE_TEXT,
    Message.TYPE_IMAGE,
    Message.TYPE_DOCUMENT,
    Message.TYPE_AUDIO,
    Message.TYPE_VIDEO,
}

DELIVERY_STATUS_RANK = {
    Message.DELIVERY_PENDING: 0,
    Message.DELIVERY_SENT: 1,
    Message.DELIVERY_DELIVERED: 2,
    Message.DELIVERY_READ: 3,
}


def valid_webhook_signature(raw_body, signature_header, app_secret):
    if not raw_body or not signature_header or not app_secret:
        return False
    algorithm, separator, supplied_digest = signature_header.partition("=")
    if algorithm != "sha256" or not separator or len(supplied_digest) != 64:
        return False
    expected_digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_digest, supplied_digest)


def webhook_phone_number_ids(payload):
    return {
        str(change.get("value", {}).get("metadata", {}).get("phone_number_id"))
        for entry in payload.get("entry", [])
        for change in entry.get("changes", [])
        if change.get("value", {}).get("metadata", {}).get("phone_number_id")
    }


def parse_unix_timestamp(value):
    if not value:
        return timezone.now()

    try:
        return datetime.fromtimestamp(int(value), tz=datetime_timezone.utc)
    except (TypeError, ValueError):
        return timezone.now()


def extract_text_messages(payload):
    events = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")
            profiles_by_wa_id = {
                contact.get("wa_id"): contact.get("profile", {}).get("name", "")
                for contact in value.get("contacts", [])
            }

            for message in value.get("messages", []):
                message_type = message.get("type")
                if message_type not in SUPPORTED_INBOUND_MESSAGE_TYPES:
                    logger.info(
                        "Ignoring unsupported WhatsApp message type=%s id=%s",
                        message_type,
                        message.get("id"),
                    )
                    continue

                sender_phone = message.get("from")
                media_payload = message.get(message_type, {}) if message_type != Message.TYPE_TEXT else {}
                events.append(
                    {
                        "phone_number_id": phone_number_id,
                        "sender_phone": sender_phone,
                        "profile_name": profiles_by_wa_id.get(sender_phone, ""),
                        "message_id": message.get("id"),
                        "timestamp": message.get("timestamp"),
                        "message_type": message_type,
                        "text": message.get("text", {}).get("body", "") if message_type == Message.TYPE_TEXT else media_payload.get("caption", ""),
                        "meta_media_id": media_payload.get("id", ""),
                        "media_mime_type": media_payload.get("mime_type", ""),
                        "media_filename": media_payload.get("filename", ""),
                    }
                )

    return events


def extract_status_events(payload):
    events = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")

            for status_event in value.get("statuses", []):
                events.append(
                    {
                        "phone_number_id": phone_number_id,
                        "message_id": status_event.get("id"),
                        "recipient_id": status_event.get("recipient_id"),
                        "status": status_event.get("status"),
                        "timestamp": status_event.get("timestamp"),
                        "errors": status_event.get("errors", []),
                    }
                )

    return events


def handle_text_message_event(event):
    phone_number_id = event.get("phone_number_id")
    message_id = event.get("message_id")
    sender_phone = event.get("sender_phone")
    text = event.get("text", "")
    message_type = event.get("message_type") or Message.TYPE_TEXT

    config = (
        WhatsAppBusinessConfig.objects.select_related("organization")
        .filter(phone_number_id=phone_number_id, is_active=True)
        .first()
    )

    if config is None:
        logger.warning("No active WhatsApp config found for phone_number_id=%s", phone_number_id)
        return "ignored"

    if not message_id or not sender_phone:
        logger.warning("Ignoring WhatsApp message with missing message_id or sender_phone")
        return "ignored"

    if Message.objects.filter(external_message_id=message_id).exists():
        logger.info("Ignoring duplicate WhatsApp message id=%s", message_id)
        return "duplicate"

    organization = config.organization
    sent_at = parse_unix_timestamp(event.get("timestamp"))

    with transaction.atomic():
        contact, created = Contact.objects.get_or_create(
            organization=organization,
            phone_number=sender_phone,
            defaults={
                "full_name": event.get("profile_name", ""),
                "source": Contact.SOURCE_WHATSAPP,
                "status": Contact.STATUS_ACTIVE,
            },
        )

        contact_changed = False
        if contact.source != Contact.SOURCE_WHATSAPP:
            contact.source = Contact.SOURCE_WHATSAPP
            contact_changed = True
        if contact.status != Contact.STATUS_ACTIVE:
            contact.status = Contact.STATUS_ACTIVE
            contact_changed = True
        if event.get("profile_name") and not contact.full_name:
            contact.full_name = event["profile_name"]
            contact_changed = True

        if contact_changed:
            contact.save(update_fields=["source", "status", "full_name", "updated_at"])

        conversation, conversation_created = Conversation.objects.get_or_create(
            organization=organization,
            contact=contact,
            channel=Conversation.CHANNEL_WHATSAPP,
            status=Conversation.STATUS_OPEN,
        )

        message = Message.objects.create(
            organization=organization,
            conversation=conversation,
            sender_type=Message.SENDER_CONTACT,
            direction=Message.DIRECTION_INBOUND,
            message_type=message_type,
            text=text,
            external_message_id=message_id,
            media_mime_type=event.get("media_mime_type", ""),
            media_filename=event.get("media_filename", ""),
            meta_media_id=event.get("meta_media_id", ""),
            delivery_status=Message.DELIVERY_DELIVERED,
            sent_at=sent_at,
        )

        conversation.last_message_at = sent_at
        conversation.save(update_fields=["last_message_at", "updated_at"])

        if created:
            create_lead_deal_for_contact(contact, organization, source="whatsapp")
            run_automations_on_commit(
                AutomationRule.TRIGGER_CONTACT_CREATED,
                organization,
                {"contact": contact},
            )
        if conversation_created:
            run_automations_on_commit(
                AutomationRule.TRIGGER_CONVERSATION_CREATED,
                organization,
                {"contact": contact, "conversation": conversation},
            )
        from .dispatching import dispatch_inbound_consumers
        transaction.on_commit(lambda: dispatch_inbound_consumers(organization, contact, conversation, message), robust=True)

    broadcast_inbox_event(
        organization.id,
        "message.created",
        conversation_id=conversation.id,
        message_id=message.id,
        contact_id=contact.id,
        delivery_status=message.delivery_status,
    )
    logger.info(
        "Processed inbound WhatsApp message id=%s type=%s phone_number_id=%s contact_created=%s",
        message.external_message_id,
        message.message_type,
        phone_number_id,
        created,
    )
    return "created"


def handle_status_event(event):
    phone_number_id = event.get("phone_number_id")
    message_id = event.get("message_id")
    status_value = event.get("status")

    config = (
        WhatsAppBusinessConfig.objects.select_related("organization")
        .filter(phone_number_id=phone_number_id, is_active=True)
        .first()
    )

    if config is None:
        logger.warning("No active WhatsApp config found for status phone_number_id=%s", phone_number_id)
        return "ignored"

    if status_value not in {
        Message.DELIVERY_SENT,
        Message.DELIVERY_DELIVERED,
        Message.DELIVERY_READ,
        Message.DELIVERY_FAILED,
    }:
        logger.info("Ignoring unsupported WhatsApp status=%s message_id=%s", status_value, message_id)
        return "ignored"

    if not message_id:
        logger.warning("Ignoring WhatsApp status event with missing message id")
        return "ignored"

    try:
        message = Message.objects.get(
            organization=config.organization,
            external_message_id=message_id,
        )
    except Message.DoesNotExist:
        logger.warning("No message found for WhatsApp status message_id=%s phone_number_id=%s", message_id, phone_number_id)
        return "not_found"

    current_rank = DELIVERY_STATUS_RANK.get(message.delivery_status)
    incoming_rank = DELIVERY_STATUS_RANK.get(status_value)
    if message.delivery_status == Message.DELIVERY_READ or (
        current_rank is not None and incoming_rank is not None and incoming_rank < current_rank
    ):
        logger.info(
            "Ignoring stale WhatsApp status message_id=%s current=%s incoming=%s",
            message_id,
            message.delivery_status,
            status_value,
        )
        return "stale"

    event_time = parse_unix_timestamp(event.get("timestamp"))
    update_fields = ["delivery_status"]
    message.delivery_status = status_value

    if status_value == Message.DELIVERY_DELIVERED:
        message.delivered_at = event_time
        update_fields.append("delivered_at")
    elif status_value == Message.DELIVERY_READ:
        if message.delivered_at is None:
            message.delivered_at = event_time
            update_fields.append("delivered_at")
        message.read_at = event_time
        update_fields.append("read_at")
    elif status_value == Message.DELIVERY_FAILED:
        safe_errors = [
            {
                "code": error.get("code"),
                "title": error.get("title"),
                "message": error.get("message"),
            }
            for error in event.get("errors", [])
        ]
        logger.warning(
            "WhatsApp message failed message_id=%s phone_number_id=%s errors=%s",
            message_id,
            phone_number_id,
            safe_errors,
        )

    message.save(update_fields=sorted(set(update_fields)))
    error_message = ""
    if status_value == Message.DELIVERY_FAILED:
        error_message = "; ".join(
            filter(
                None,
                [
                    error.get("message") or error.get("title")
                    for error in event.get("errors", [])
                ],
            )
        )
    update_recipient_from_webhook(
        message_id,
        status_value,
        event_time=event_time,
        error_message=error_message,
        organization=config.organization,
    )
    broadcast_inbox_event(
        config.organization_id,
        "message.status_updated",
        conversation_id=message.conversation_id,
        message_id=message.id,
        contact_id=message.conversation.contact_id,
        delivery_status=message.delivery_status,
    )
    logger.info("Updated WhatsApp message status message_id=%s status=%s", message_id, status_value)
    return "updated"
