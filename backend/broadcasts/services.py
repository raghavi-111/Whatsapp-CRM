import re

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from contacts.models import Contact
from conversations.models import Conversation, Message
from realtime.utils import broadcast_inbox_event
from templates.models import MessageTemplate
from whatsapp.models import WhatsAppBusinessConfig
from whatsapp.sending import WhatsAppSendError, send_whatsapp_template_message

from .models import BroadcastCampaign, BroadcastRecipient


VARIABLE_PATTERN = re.compile(r"{{\s*(\d+)\s*}}")
RECIPIENT_STATUS_RANK = {
    BroadcastRecipient.STATUS_PENDING: 0,
    BroadcastRecipient.STATUS_SENT: 1,
    BroadcastRecipient.STATUS_DELIVERED: 2,
    BroadcastRecipient.STATUS_READ: 3,
}


def extract_template_variables(template):
    numbers = {int(match) for match in VARIABLE_PATTERN.findall(template.body_text or "")}
    return list(range(1, max(numbers) + 1)) if numbers else []


def resolve_recipients(organization, audience_type, selected_tags=None, contact_status="", contact_source=""):
    contacts = Contact.objects.filter(organization=organization).exclude(phone_number="")

    if audience_type == BroadcastCampaign.AUDIENCE_TAGS:
        tag_ids = [tag.id if hasattr(tag, "id") else int(tag) for tag in selected_tags or []]
        contacts = contacts.filter(tags__id__in=tag_ids).distinct()
    elif audience_type == BroadcastCampaign.AUDIENCE_FILTERS:
        if contact_status:
            contacts = contacts.filter(status=contact_status)
        if contact_source:
            contacts = contacts.filter(source=contact_source)

    return contacts.order_by("id")


def estimate_recipients(organization, audience_type, selected_tags=None, contact_status="", contact_source=""):
    return resolve_recipients(
        organization,
        audience_type,
        selected_tags=selected_tags,
        contact_status=contact_status,
        contact_source=contact_source,
    ).count()


def render_parameter(contact, mapping):
    mapping_type = mapping.get("type", "")
    if mapping_type == "contact_name":
        return contact.full_name or contact.phone_number
    if mapping_type == "phone_number":
        return contact.phone_number
    if mapping_type == "company":
        return contact.company_name
    if mapping_type == "static":
        return str(mapping.get("value", ""))
    return ""


def build_parameters(contact, mappings):
    return [render_parameter(contact, mapping) for mapping in mappings or []]


def render_template_preview(template, parameters):
    text = template.body_text
    for index, value in enumerate(parameters or [], start=1):
        text = text.replace(f"{{{{{index}}}}}", str(value))
    return text


def refresh_campaign_counters(campaign):
    counts = {
        row["status"]: row["count"]
        for row in campaign.recipients.values("status").annotate(count=Count("id"))
    }
    campaign.recipient_count = sum(counts.values())
    campaign.sent_count = (
        counts.get(BroadcastRecipient.STATUS_SENT, 0)
        + counts.get(BroadcastRecipient.STATUS_DELIVERED, 0)
        + counts.get(BroadcastRecipient.STATUS_READ, 0)
    )
    campaign.delivered_count = counts.get(BroadcastRecipient.STATUS_DELIVERED, 0) + counts.get(BroadcastRecipient.STATUS_READ, 0)
    campaign.read_count = counts.get(BroadcastRecipient.STATUS_READ, 0)
    campaign.failed_count = counts.get(BroadcastRecipient.STATUS_FAILED, 0)
    campaign.save(
        update_fields=[
            "recipient_count",
            "sent_count",
            "delivered_count",
            "read_count",
            "failed_count",
            "updated_at",
        ]
    )


def create_recipients_for_campaign(campaign):
    contacts = resolve_recipients(
        campaign.organization,
        campaign.audience_type,
        selected_tags=campaign.selected_tags.all(),
        contact_status=campaign.contact_status,
        contact_source=campaign.contact_source,
    )
    recipients = []
    for contact in contacts:
        recipient, _ = BroadcastRecipient.objects.get_or_create(
            campaign=campaign,
            contact=contact,
            defaults={"phone": contact.phone_number},
        )
        recipients.append(recipient)
    campaign.recipient_count = len(recipients)
    campaign.save(update_fields=["recipient_count", "updated_at"])
    return recipients


def send_campaign_now(campaign):
    with transaction.atomic():
        campaign = BroadcastCampaign.objects.select_for_update().get(id=campaign.id)
        if campaign.status not in [BroadcastCampaign.STATUS_DRAFT, BroadcastCampaign.STATUS_SCHEDULED]:
            raise ValueError("Campaign has already started or cannot be sent.")
        if campaign.template.status != MessageTemplate.STATUS_APPROVED:
            raise ValueError("Only approved templates can be sent.")
        campaign.status = BroadcastCampaign.STATUS_QUEUED
        campaign.save(update_fields=["status", "updated_at"])
        recipients = create_recipients_for_campaign(campaign)

    campaign.status = BroadcastCampaign.STATUS_SENDING
    campaign.save(update_fields=["status", "updated_at"])

    config = WhatsAppBusinessConfig.objects.filter(organization=campaign.organization, is_active=True).first()
    sent_at = timezone.now()

    for recipient in recipients:
        if recipient.status != BroadcastRecipient.STATUS_PENDING:
            continue
        contact = recipient.contact
        if contact is None:
            recipient.status = BroadcastRecipient.STATUS_FAILED
            recipient.error_message = "Contact no longer exists."
            recipient.save(update_fields=["status", "error_message", "updated_at"])
            continue

        conversation, _ = Conversation.objects.get_or_create(
            organization=campaign.organization,
            contact=contact,
            channel=Conversation.CHANNEL_WHATSAPP,
            status=Conversation.STATUS_OPEN,
        )
        parameters = build_parameters(contact, campaign.variable_mappings)
        message_text = render_template_preview(campaign.template, parameters)

        try:
            result = send_whatsapp_template_message(
                config=config,
                to_phone_number=recipient.phone,
                template_name=campaign.template.name,
                language=campaign.template_language,
                parameters=parameters,
            )
            message = Message.objects.create(
                organization=campaign.organization,
                conversation=conversation,
                sender_type=Message.SENDER_AGENT,
                direction=Message.DIRECTION_OUTBOUND,
                message_type=Message.TYPE_TEMPLATE,
                text=message_text,
                external_message_id=result.external_message_id,
                delivery_status=Message.DELIVERY_SENT,
                sent_at=sent_at,
            )
            recipient.status = BroadcastRecipient.STATUS_SENT
            recipient.whatsapp_message_id = result.external_message_id
            recipient.sent_at = sent_at
            recipient.error_message = ""
            recipient.save(update_fields=["status", "whatsapp_message_id", "sent_at", "error_message", "updated_at"])
            conversation.last_message_at = message.sent_at or message.created_at
            conversation.save(update_fields=["last_message_at", "updated_at"])
            broadcast_inbox_event(
                campaign.organization_id,
                "message.created",
                conversation_id=conversation.id,
                message_id=message.id,
                contact_id=contact.id,
                delivery_status=message.delivery_status,
            )
        except WhatsAppSendError as error:
            recipient.status = BroadcastRecipient.STATUS_FAILED
            recipient.error_message = str(error)
            recipient.save(update_fields=["status", "error_message", "updated_at"])

    refresh_campaign_counters(campaign)
    campaign.refresh_from_db()
    campaign.status = BroadcastCampaign.STATUS_FAILED if campaign.sent_count == 0 and campaign.failed_count > 0 else BroadcastCampaign.STATUS_COMPLETED
    campaign.save(update_fields=["status", "updated_at"])
    if campaign.status == BroadcastCampaign.STATUS_COMPLETED:
        try:
            from automations.models import AutomationRule
            from automations.services import enqueue_automations

            enqueue_automations(
                AutomationRule.TRIGGER_BROADCAST_COMPLETED,
                campaign.organization,
                {"broadcast": campaign, "broadcast_id": campaign.id},
            )
        except Exception:
            pass
    return campaign


def update_recipient_from_webhook(message_id, status_value, event_time=None, error_message="", organization=None):
    recipients = BroadcastRecipient.objects.select_related("campaign").filter(whatsapp_message_id=message_id)
    if organization is not None:
        recipients = recipients.filter(campaign__organization=organization)
    recipient = recipients.first()
    if recipient is None:
        return None

    current_rank = RECIPIENT_STATUS_RANK.get(recipient.status)
    incoming_rank = RECIPIENT_STATUS_RANK.get(status_value)
    if recipient.status == BroadcastRecipient.STATUS_READ or (
        current_rank is not None and incoming_rank is not None and incoming_rank < current_rank
    ):
        return recipient

    event_time = event_time or timezone.now()
    update_fields = ["status", "updated_at"]
    if status_value == Message.DELIVERY_DELIVERED:
        recipient.status = BroadcastRecipient.STATUS_DELIVERED
        recipient.delivered_at = event_time
        update_fields.append("delivered_at")
    elif status_value == Message.DELIVERY_READ:
        recipient.status = BroadcastRecipient.STATUS_READ
        recipient.read_at = event_time
        if recipient.delivered_at is None:
            recipient.delivered_at = event_time
            update_fields.append("delivered_at")
        update_fields.append("read_at")
    elif status_value == Message.DELIVERY_FAILED:
        recipient.status = BroadcastRecipient.STATUS_FAILED
        recipient.error_message = error_message
        update_fields.append("error_message")
    elif status_value == Message.DELIVERY_SENT:
        recipient.status = BroadcastRecipient.STATUS_SENT
    recipient.save(update_fields=sorted(set(update_fields)))
    refresh_campaign_counters(recipient.campaign)
    return recipient
