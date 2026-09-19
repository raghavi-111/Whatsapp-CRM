import uuid

from django.db import transaction
from django.utils import timezone

from contacts.models import Contact
from conversations.models import Conversation, Message
from realtime.utils import broadcast_inbox_event
from .dispatching import dispatch_inbound_consumers


def simulate_inbound_message(organization, *, text, conversation=None, phone_number="", message_id=""):
    external_id = message_id.strip() if message_id else f"simulated-{uuid.uuid4()}"
    duplicate = Message.objects.filter(organization=organization, external_message_id=external_id).first()
    if duplicate:
        return duplicate, True

    with transaction.atomic():
        if conversation is not None:
            conversation = Conversation.objects.select_related("contact").get(id=conversation.id, organization=organization)
            contact = conversation.contact
        else:
            contact, _ = Contact.objects.get_or_create(organization=organization, phone_number=phone_number, defaults={"source": Contact.SOURCE_WHATSAPP, "status": Contact.STATUS_ACTIVE})
            conversation, _ = Conversation.objects.get_or_create(organization=organization, contact=contact, channel=Conversation.CHANNEL_WHATSAPP, status=Conversation.STATUS_OPEN)
        message = Message.objects.create(organization=organization, conversation=conversation, sender_type=Message.SENDER_CONTACT, direction=Message.DIRECTION_INBOUND, message_type=Message.TYPE_TEXT, text=text, external_message_id=external_id, delivery_status=Message.DELIVERY_DELIVERED, sent_at=timezone.now())
        conversation.last_message_at = message.sent_at
        conversation.save(update_fields=["last_message_at", "updated_at"])

    # The inner atomic block has committed before either engine is invoked.
    dispatch_inbound_consumers(organization, contact, conversation, message, simulation=True)

    broadcast_inbox_event(organization.id, "message.created", conversation_id=conversation.id, message_id=message.id, contact_id=contact.id, delivery_status=message.delivery_status)
    return message, False
