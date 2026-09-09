import logging

from celery import shared_task

from contacts.models import Contact
from conversations.models import Conversation, Message
from organizations.models import Organization
from support.models import Tag
from pipelines.models import Deal
from broadcasts.models import BroadcastCampaign

from .services import run_automations


logger = logging.getLogger(__name__)


@shared_task(bind=True, name="automations.run_automation_task")
def run_automation_task(self, trigger_type, organization_id, context):
    organization = Organization.objects.filter(id=organization_id).first()
    if organization is None:
        logger.warning(
            "Skipping automation task because organization was not found trigger_type=%s organization_id=%s",
            trigger_type,
            organization_id,
        )
        return {"status": "skipped", "reason": "organization_not_found"}

    hydrated_context = hydrate_context(organization, context or {})
    logger.info(
        "Running automation task trigger_type=%s organization_id=%s task_id=%s",
        trigger_type,
        organization_id,
        self.request.id,
    )
    run_automations(trigger_type, organization, hydrated_context)
    return {"status": "completed"}


def hydrate_context(organization, context):
    hydrated = {
        "message_text": context.get("message_text", ""),
        "tag_name": context.get("tag_name", ""),
        "previous_status": context.get("previous_status", ""),
        "conversation_status": context.get("conversation_status", ""),
        "previous_stage": context.get("previous_stage", ""),
        "deal_stage": context.get("deal_stage", ""),
    }

    contact_id = context.get("contact_id")
    conversation_id = context.get("conversation_id")
    message_id = context.get("message_id")
    tag_id = context.get("tag_id")
    deal_id = context.get("deal_id")
    broadcast_id = context.get("broadcast_id")

    if contact_id:
        hydrated["contact"] = Contact.objects.filter(id=contact_id, organization=organization).first()
    if conversation_id:
        hydrated["conversation"] = Conversation.objects.filter(id=conversation_id, organization=organization).first()
    if message_id:
        hydrated["message"] = Message.objects.filter(id=message_id, organization=organization).first()
    if tag_id:
        hydrated["tag"] = Tag.objects.filter(id=tag_id, organization=organization).first()
    if deal_id:
        hydrated["deal"] = Deal.objects.filter(id=deal_id, organization=organization).first()
    if broadcast_id:
        hydrated["broadcast"] = BroadcastCampaign.objects.filter(id=broadcast_id, organization=organization).first()

    if hydrated.get("contact") is None and hydrated.get("conversation") is not None:
        hydrated["contact"] = hydrated["conversation"].contact
    if hydrated.get("conversation") is None and hydrated.get("message") is not None:
        hydrated["conversation"] = hydrated["message"].conversation
    if hydrated.get("contact") is None and hydrated.get("message") is not None:
        hydrated["contact"] = hydrated["message"].conversation.contact
    if hydrated.get("contact") is None and hydrated.get("deal") is not None:
        hydrated["contact"] = hydrated["deal"].contact

    return hydrated
