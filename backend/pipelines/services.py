from django.db import IntegrityError, transaction

from .models import Deal


def build_contact_deal_title(contact):
    label = contact.full_name or contact.phone_number or "WhatsApp lead"
    return f"{label} lead"


def create_lead_deal_for_contact(contact, organization, source=Deal.SOURCE_WHATSAPP):
    if contact is None:
        return None, False

    existing_deal = Deal.objects.filter(
        organization=organization,
        contact=contact,
        status=Deal.STATUS_OPEN,
    ).first()
    if existing_deal:
        return existing_deal, False

    try:
        with transaction.atomic():
            deal = Deal.objects.create(
                organization=organization,
                contact=contact,
                title=build_contact_deal_title(contact),
                stage=Deal.STAGE_NEW,
                status=Deal.STATUS_OPEN,
                source=source,
            )
            enqueue_deal_created_automation(deal)
            return deal, True
    except IntegrityError:
        return Deal.objects.filter(
            organization=organization,
            contact=contact,
            status=Deal.STATUS_OPEN,
        ).first(), False


def enqueue_deal_created_automation(deal):
    try:
        from automations.models import AutomationRule
        from automations.services import run_automations_on_commit

        run_automations_on_commit(
            AutomationRule.TRIGGER_DEAL_CREATED,
            deal.organization,
            {"contact": deal.contact, "deal": deal, "deal_stage": deal.stage},
        )
    except Exception:
        return
