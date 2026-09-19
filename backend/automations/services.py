import logging

from django.db import transaction
from django.utils import timezone

from conversations.models import Conversation, Message
from organizations.models import OrganizationMember
from realtime.utils import broadcast_inbox_event
from support.models import ContactNote, ConversationNote, Tag
from templates.models import MessageTemplate
from whatsapp.models import WhatsAppBusinessConfig
from whatsapp.sending import WhatsAppSendError, send_whatsapp_media_message, send_whatsapp_template_message, send_whatsapp_text_message, upload_whatsapp_media
from pipelines.models import Deal
from pipelines.services import create_lead_deal_for_contact

from .models import AutomationLog, AutomationMedia, AutomationRule


logger = logging.getLogger(__name__)


def run_automations(trigger_type, organization, context):
    rules = AutomationRule.objects.filter(
        organization=organization,
        trigger_type=trigger_type,
        is_active=True,
    )

    for rule in rules:
        safe_context = build_safe_context(context)
        try:
            if already_processed_message(rule, safe_context):
                AutomationLog.objects.create(
                    organization=organization,
                    rule=rule,
                    trigger_type=trigger_type,
                    status=AutomationLog.STATUS_SKIPPED,
                    message="Automation already ran for this message.",
                    context_json=safe_context,
                )
                continue

            matched, condition_results = conditions_match(rule.conditions_json, context, rule.condition_logic)
            if not matched:
                AutomationLog.objects.create(
                    organization=organization,
                    rule=rule,
                    trigger_type=trigger_type,
                    status=AutomationLog.STATUS_SKIPPED,
                    message="Conditions did not match.",
                    context_json=safe_context,
                    matched_conditions_json=condition_results,
                )
                continue

            actions_executed = execute_actions(rule.actions_json, organization, context)
            AutomationLog.objects.create(
                organization=organization,
                rule=rule,
                trigger_type=trigger_type,
                status=AutomationLog.STATUS_SUCCESS,
                message=f"Automation ran successfully. Actions executed: {len(actions_executed)}.",
                context_json=safe_context,
                matched_conditions_json=condition_results,
                actions_executed_json=actions_executed,
            )
        except Exception as error:
            logger.exception("Automation failed rule_id=%s trigger_type=%s", rule.id, trigger_type)
            AutomationLog.objects.create(
                organization=organization,
                rule=rule,
                trigger_type=trigger_type,
                status=AutomationLog.STATUS_FAILED,
                message=str(error)[:500],
                context_json=safe_context,
                actions_executed_json=getattr(error, "action_results", []),
                error_message=str(error)[:1000],
            )


def already_processed_message(rule, safe_context):
    message_id = safe_context.get("message_id")
    if not message_id:
        return False
    return AutomationLog.objects.filter(
        rule=rule,
        status=AutomationLog.STATUS_SUCCESS,
        context_json__message_id=message_id,
    ).exists()


def conditions_match(conditions, context, logic=AutomationRule.CONDITION_LOGIC_AND):
    results = []
    for condition in conditions or []:
        matched = evaluate_condition(condition, context)
        results.append({**condition, "matched": matched})

    if not results:
        return True, results
    if logic == AutomationRule.CONDITION_LOGIC_OR:
        return any(result["matched"] for result in results), results
    return all(result["matched"] for result in results), results


def evaluate_condition(condition, context):
        field = condition.get("field")
        operator = condition.get("operator", "equals")
        expected = condition.get("value", "")
        message_text = getattr(context.get("message"), "text", "") or context.get("message_text", "")

        if field == "contact_source":
            actual = getattr(context.get("contact"), "source", "")
            return compare(actual, expected, operator)
        if field == "contact_status":
            actual = getattr(context.get("contact"), "status", "")
            return compare(actual, expected, operator)
        if field in {"message_text_contains", "message_text_equals", "message_text_starts_with", "message_text_ends_with"}:
            implied_operator = {
                "message_text_contains": "icontains",
                "message_text_equals": "equals",
                "message_text_starts_with": "starts_with",
                "message_text_ends_with": "ends_with",
            }[field]
            return compare(message_text, expected, operator if operator != "equals" and field == "message_text_contains" else implied_operator)
        if field == "conversation_status":
            actual = getattr(context.get("conversation"), "status", "")
            return compare(actual, expected, operator)
        if field == "contact_has_tag":
            contact = context.get("contact")
            return contact is not None and contact.tags.filter(name__iexact=str(expected)).exists()
        if field == "contact_does_not_have_tag":
            contact = context.get("contact")
            return contact is not None and not contact.tags.filter(name__iexact=str(expected)).exists()
        if field == "deal_stage":
            deal = context.get("deal") or get_open_deal(context)
            return deal is not None and compare(deal.stage, expected, operator)
        if field == "assigned_user":
            conversation = context.get("conversation")
            return conversation is not None and compare(str(conversation.assigned_to_id or ""), str(expected), operator)
        if field == "first_message":
            conversation = context.get("conversation")
            message = context.get("message")
            if conversation is None or message is None:
                return False
            return not Message.objects.filter(
                conversation=conversation,
                direction=Message.DIRECTION_INBOUND,
                created_at__lt=message.created_at,
            ).exists()
        if field == "business_hours":
            hour = timezone.localtime().hour
            start = int(condition.get("start_hour", 9))
            end = int(condition.get("end_hour", 18))
            inside = start <= hour < end if start < end else hour >= start or hour < end
            expected_inside = str(expected or "inside").lower() != "outside"
            return inside if expected_inside else not inside
        return False


def compare(actual, expected, operator):
    if operator in ["contains", "icontains"]:
        return str(expected).lower() in str(actual).lower()
    if operator == "starts_with":
        return str(actual).lower().startswith(str(expected).lower())
    if operator == "ends_with":
        return str(actual).lower().endswith(str(expected).lower())
    if operator == "not_equals":
        return str(actual).lower() != str(expected).lower()
    return str(actual).lower() == str(expected).lower()


def execute_actions(actions, organization, context):
    results = []
    for action in actions or []:
        action_type = action.get("type")
        try:
            result = None
            if action_type == "add_tag": add_tag(organization, context, action)
            elif action_type == "remove_tag": remove_tag(organization, context, action)
            elif action_type == "assign_agent": assign_agent(organization, context, action)
            elif action_type == "update_conversation_status": update_conversation_status(organization, context, action)
            elif action_type == "send_message": result = send_message(organization, context, action)
            elif action_type == "send_template": result = send_template(organization, context, action)
            elif action_type in {"send_image", "send_document", "send_brochure", "send_video", "send_audio", "send_media"}: result = send_media(organization, context, action)
            elif action_type == "create_deal": create_deal(organization, context, action)
            elif action_type == "update_deal_stage": update_deal_stage(organization, context, action)
            elif action_type == "create_notification": create_notification(organization, context, action)
            elif action_type == "add_conversation_note": add_conversation_note(organization, context, action)
            elif action_type == "add_contact_note": add_contact_note(organization, context, action)
            elif action_type == "stop":
                results.append({"action_type": action_type, "status": "success", "whatsapp_message_id": ""})
                break
            else: raise ValueError(f"Unsupported action type: {action_type}.")
            results.append({"action_type": action_type, "status": "success", "whatsapp_message_id": getattr(result, "external_message_id", "") if result else ""})
        except Exception as error:
            results.append({"action_type": action_type, "status": "failed", "whatsapp_message_id": "", "error_message": str(error)})
            error.action_results = results
            raise
    return results


def add_tag(organization, context, action):
    contact = require_contact(context)
    tag_name = str(action.get("tag_name", "")).strip()
    if not tag_name:
        raise ValueError("add_tag action requires tag_name.")

    tag, _ = Tag.objects.get_or_create(
        organization=organization,
        name=tag_name,
        defaults={"color": action.get("color") or "#128c7e"},
    )
    contact.tags.add(tag)
    broadcast_inbox_event(organization.id, "contact.tags_updated", contact_id=contact.id)


def remove_tag(organization, context, action):
    contact = require_contact(context)
    tag_name = str(action.get("tag_name", "")).strip()
    tag = Tag.objects.filter(organization=organization, name__iexact=tag_name).first()
    if tag:
        contact.tags.remove(tag)
        broadcast_inbox_event(organization.id, "contact.tags_updated", contact_id=contact.id)


def assign_agent(organization, context, action):
    conversation = require_conversation(context)
    agent = None
    agent_id = action.get("agent_id") or action.get("user_id")
    agent_email = str(action.get("agent_email", "")).strip()

    memberships = OrganizationMember.objects.select_related("user").filter(
        organization=organization,
        status=OrganizationMember.STATUS_ACTIVE,
    )
    if agent_id:
        membership = memberships.filter(user_id=agent_id).first()
        agent = membership.user if membership else None
    elif agent_email:
        membership = memberships.filter(user__email__iexact=agent_email).first()
        agent = membership.user if membership else None

    if agent is None:
        raise ValueError("assign_agent action requires an active organization member.")

    conversation.assigned_to = agent
    conversation.save(update_fields=["assigned_to", "updated_at"])
    broadcast_inbox_event(
        organization.id,
        "conversation.assigned",
        conversation_id=conversation.id,
        contact_id=conversation.contact_id,
    )


def update_conversation_status(organization, context, action):
    conversation = require_conversation(context)
    next_status = str(action.get("status", "")).strip()
    allowed_statuses = [choice[0] for choice in Conversation.STATUS_CHOICES]
    if next_status not in allowed_statuses:
        raise ValueError("update_conversation_status action has an invalid status.")

    conversation.status = next_status
    conversation.save(update_fields=["status", "updated_at"])
    broadcast_inbox_event(
        organization.id,
        "conversation.status_updated",
        conversation_id=conversation.id,
        contact_id=conversation.contact_id,
    )


def send_message(organization, context, action):
    contact = require_contact(context)
    conversation = context.get("conversation")
    message_text = str(action.get("text", "")).strip()
    if not message_text:
        raise ValueError("send_message action requires text.")

    if conversation is None:
        conversation, _ = Conversation.objects.get_or_create(
            organization=organization,
            contact=contact,
            channel=Conversation.CHANNEL_WHATSAPP,
            status=Conversation.STATUS_OPEN,
        )

    sent_at = timezone.now()
    config = WhatsAppBusinessConfig.objects.filter(organization=organization, is_active=True).first()

    try:
        send_result = send_whatsapp_text_message(
            config=config,
            to_phone_number=contact.phone_number,
            text=message_text,
        )
        delivery_status = Message.DELIVERY_SENT
        external_message_id = send_result.external_message_id
    except WhatsAppSendError as error:
        delivery_status = Message.DELIVERY_FAILED
        external_message_id = ""
        raise ValueError(str(error)) from error
    finally:
        if "delivery_status" in locals():
            message = Message.objects.create(
                organization=organization,
                conversation=conversation,
                sender_type=Message.SENDER_SYSTEM,
                direction=Message.DIRECTION_OUTBOUND,
                message_type=Message.TYPE_TEXT,
                text=message_text,
                external_message_id=external_message_id,
                delivery_status=delivery_status,
                sent_at=sent_at,
            )
            conversation.last_message_at = message.sent_at or message.created_at
            conversation.save(update_fields=["last_message_at", "updated_at"])
            broadcast_inbox_event(
                organization.id,
                "message.created",
                conversation_id=conversation.id,
                message_id=message.id,
                contact_id=contact.id,
                delivery_status=message.delivery_status,
            )
    return send_result


def send_media(organization, context, action):
    contact = require_contact(context)
    conversation = context.get("conversation")
    if conversation is None:
        conversation, _ = Conversation.objects.get_or_create(organization=organization, contact=contact, channel=Conversation.CHANNEL_WHATSAPP, status=Conversation.STATUS_OPEN)
    media_type = {"send_image": "image", "send_document": "document", "send_brochure": "document", "send_video": "video", "send_audio": "audio"}.get(action.get("type"), action.get("media_type"))
    if media_type not in {"image", "document", "video", "audio"}:
        raise ValueError("Media action has an invalid media type.")

    asset = None
    file_url = str(action.get("file_url", "")).strip()
    filename = str(action.get("filename", "")).strip()
    mime_type = str(action.get("mime_type", "")).strip()
    if action.get("media_id"):
        asset = AutomationMedia.objects.filter(id=action["media_id"], organization=organization, media_type=media_type).first()
        if asset is None:
            raise ValueError("Automation media is missing or belongs to another organization.")
        filename, mime_type = asset.filename, asset.mime_type
    elif not file_url.lower().startswith("https://"):
        raise ValueError("Media URL must be a public HTTPS URL.")

    config = WhatsAppBusinessConfig.objects.filter(organization=organization, is_active=True).first()
    meta_media_id = ""
    try:
        if asset:
            try:
                with asset.file.open("rb") as media_file:
                    meta_media_id, _ = upload_whatsapp_media(config, media_file, mime_type)
            except (FileNotFoundError, OSError) as error:
                raise ValueError("Selected media file is missing or inaccessible.") from error
        send_result = send_whatsapp_media_message(config, contact.phone_number, media_type, meta_media_id=meta_media_id, media_url=file_url, caption=str(action.get("caption", ""))[:1024], filename=filename)
        delivery_status, external_message_id = Message.DELIVERY_SENT, send_result.external_message_id
    except WhatsAppSendError as error:
        delivery_status, external_message_id = Message.DELIVERY_FAILED, ""
        raise ValueError(str(error)) from error
    finally:
        if "delivery_status" in locals():
            message = Message.objects.create(organization=organization, conversation=conversation, sender_type=Message.SENDER_SYSTEM, direction=Message.DIRECTION_OUTBOUND, message_type=media_type, text=str(action.get("caption", ""))[:1024], media_file=asset.file.name if asset else "", media_url=file_url, media_mime_type=mime_type, media_filename=filename, media_size=asset.size if asset else 0, meta_media_id=meta_media_id, external_message_id=external_message_id, delivery_status=delivery_status, sent_at=timezone.now())
            conversation.last_message_at = message.sent_at or message.created_at
            conversation.save(update_fields=["last_message_at", "updated_at"])
            broadcast_inbox_event(organization.id, "message.created", conversation_id=conversation.id, message_id=message.id, contact_id=contact.id, delivery_status=message.delivery_status)
    return send_result


def send_template(organization, context, action):
    contact = require_contact(context)
    conversation = context.get("conversation")
    template = get_approved_template(organization, action)
    parameters = action.get("parameters") or build_template_parameters(context, action.get("parameter_mappings") or [])
    if not isinstance(parameters, list):
        raise ValueError("send_template parameters must be a JSON array.")

    if conversation is None:
        conversation, _ = Conversation.objects.get_or_create(
            organization=organization,
            contact=contact,
            channel=Conversation.CHANNEL_WHATSAPP,
            status=Conversation.STATUS_OPEN,
        )

    message_text = render_template_preview(template, parameters)
    sent_at = timezone.now()
    config = WhatsAppBusinessConfig.objects.filter(organization=organization, is_active=True).first()

    try:
        send_result = send_whatsapp_template_message(
            config=config,
            to_phone_number=contact.phone_number,
            template_name=template.name,
            language=template.language,
            parameters=parameters,
        )
        delivery_status = Message.DELIVERY_SENT
        external_message_id = send_result.external_message_id
    except WhatsAppSendError as error:
        delivery_status = Message.DELIVERY_FAILED
        external_message_id = ""
        raise ValueError(str(error)) from error
    finally:
        if "delivery_status" in locals():
            message = Message.objects.create(
                organization=organization,
                conversation=conversation,
                sender_type=Message.SENDER_AGENT,
                direction=Message.DIRECTION_OUTBOUND,
                message_type=Message.TYPE_TEMPLATE,
                text=message_text,
                external_message_id=external_message_id,
                delivery_status=delivery_status,
                sent_at=sent_at,
            )
            conversation.last_message_at = message.sent_at or message.created_at
            conversation.save(update_fields=["last_message_at", "updated_at"])
            broadcast_inbox_event(
                organization.id,
                "message.created",
                conversation_id=conversation.id,
                message_id=message.id,
                contact_id=contact.id,
                delivery_status=message.delivery_status,
            )
    return send_result


def build_template_parameters(context, mappings):
    contact = context.get("contact")
    message_text = getattr(context.get("message"), "text", "") or context.get("message_text", "")
    values = []
    for mapping in mappings:
        mapping_type = mapping.get("type")
        if mapping_type == "contact_name":
            values.append(getattr(contact, "full_name", "") or getattr(contact, "phone_number", ""))
        elif mapping_type == "phone_number":
            values.append(getattr(contact, "phone_number", ""))
        elif mapping_type == "company":
            values.append(getattr(contact, "company_name", ""))
        elif mapping_type == "message_text":
            values.append(message_text)
        elif mapping_type == "static":
            values.append(str(mapping.get("value", "")))
        else:
            values.append("")
    return values


def get_open_deal(context):
    contact = context.get("contact")
    deal = context.get("deal")
    if deal is not None:
        return deal
    if contact is None:
        return None
    return Deal.objects.filter(organization=contact.organization, contact=contact, status=Deal.STATUS_OPEN).first()


def create_deal(organization, context, action):
    contact = require_contact(context)
    deal, _ = create_lead_deal_for_contact(contact, organization, source=action.get("source") or Deal.SOURCE_WHATSAPP)
    if deal and action.get("stage"):
        deal.stage = action["stage"]
        if deal.stage == Deal.STAGE_WON:
            deal.status = Deal.STATUS_WON
        else:
            deal.status = Deal.STATUS_OPEN
        deal.save(update_fields=["stage", "status", "updated_at"])
    context["deal"] = deal


def update_deal_stage(organization, context, action):
    deal = get_open_deal(context)
    if deal is None:
        if action.get("create_if_missing", True):
            create_deal(organization, context, action)
            deal = context.get("deal")
        else:
            raise ValueError("No open deal found for contact.")
    stage = str(action.get("stage", "")).strip()
    allowed_stages = [choice[0] for choice in Deal.STAGE_CHOICES]
    if stage not in allowed_stages:
        raise ValueError("update_deal_stage action has an invalid stage.")
    deal.stage = stage
    deal.status = Deal.STATUS_WON if stage == Deal.STAGE_WON else Deal.STATUS_OPEN
    deal.save(update_fields=["stage", "status", "updated_at"])
    context["deal"] = deal


def create_notification(organization, context, action):
    note = str(action.get("message", "")).strip()
    if not note:
        raise ValueError("create_notification action requires message.")
    contact = context.get("contact")
    conversation = context.get("conversation")
    if conversation is not None:
        ConversationNote.objects.create(organization=organization, conversation=conversation, note=f"Notification: {note}")
        broadcast_inbox_event(organization.id, "conversation.note_created", conversation_id=conversation.id, contact_id=conversation.contact_id)
    elif contact is not None:
        ContactNote.objects.create(organization=organization, contact=contact, note=f"Notification: {note}")
        broadcast_inbox_event(organization.id, "contact.note_created", contact_id=contact.id)


def add_conversation_note(organization, context, action):
    conversation = require_conversation(context)
    note_text = str(action.get("note", "")).strip()
    if not note_text:
        raise ValueError("add_conversation_note action requires note.")

    ConversationNote.objects.create(organization=organization, conversation=conversation, note=note_text)
    broadcast_inbox_event(
        organization.id,
        "conversation.note_created",
        conversation_id=conversation.id,
        contact_id=conversation.contact_id,
    )


def add_contact_note(organization, context, action):
    contact = require_contact(context)
    note_text = str(action.get("note", "")).strip()
    if not note_text:
        raise ValueError("add_contact_note action requires note.")

    ContactNote.objects.create(organization=organization, contact=contact, note=note_text)
    broadcast_inbox_event(organization.id, "contact.note_created", contact_id=contact.id)


def get_approved_template(organization, action):
    template_id = action.get("template_id")
    template_name = str(action.get("template_name", "")).strip()
    language = str(action.get("language", "")).strip().lower()

    templates = MessageTemplate.objects.filter(
        organization=organization,
        status=MessageTemplate.STATUS_APPROVED,
    )
    if template_id:
        template = templates.filter(id=template_id).first()
    else:
        template = templates.filter(name=template_name, language=language).first()

    if template is None:
        raise ValueError("send_template action requires an approved template.")
    return template


def render_template_preview(template, parameters):
    text = template.body_text
    for index, value in enumerate(parameters or [], start=1):
        text = text.replace(f"{{{{{index}}}}}", str(value))
    return text


def require_contact(context):
    contact = context.get("contact")
    if contact is None:
        raise ValueError("This action requires a contact in the automation context.")
    return contact


def require_conversation(context):
    conversation = context.get("conversation")
    if conversation is None:
        raise ValueError("This action requires a conversation in the automation context.")
    return conversation


def build_safe_context(context):
    contact = context.get("contact")
    conversation = context.get("conversation")
    message = context.get("message")
    tag = context.get("tag")
    deal = context.get("deal")
    broadcast = context.get("broadcast")

    return {
        "contact_id": getattr(contact, "id", None),
        "contact_source": getattr(contact, "source", ""),
        "conversation_id": getattr(conversation, "id", None),
        "conversation_status": getattr(conversation, "status", ""),
        "message_id": getattr(message, "id", None),
        "message_text_preview": (getattr(message, "text", "") or context.get("message_text", ""))[:120],
        "tag_id": getattr(tag, "id", None),
        "tag_name": getattr(tag, "name", context.get("tag_name", "")),
        "deal_id": getattr(deal, "id", None),
        "deal_stage": getattr(deal, "stage", context.get("deal_stage", "")),
        "broadcast_id": getattr(broadcast, "id", None),
    }


def build_task_context(context):
    contact = context.get("contact")
    conversation = context.get("conversation")
    message = context.get("message")
    tag = context.get("tag")
    deal = context.get("deal")
    broadcast = context.get("broadcast")

    return {
        "contact_id": getattr(contact, "id", None),
        "conversation_id": getattr(conversation, "id", None),
        "message_id": getattr(message, "id", None),
        "message_text": (getattr(message, "text", "") or context.get("message_text", ""))[:1000],
        "tag_id": getattr(tag, "id", None),
        "tag_name": getattr(tag, "name", context.get("tag_name", "")),
        "deal_id": getattr(deal, "id", None),
        "broadcast_id": getattr(broadcast, "id", None),
        "previous_status": context.get("previous_status", ""),
        "conversation_status": context.get("conversation_status", ""),
        "previous_stage": context.get("previous_stage", ""),
        "deal_stage": context.get("deal_stage", ""),
    }


def enqueue_automations(trigger_type, organization, context):
    task_context = build_task_context(context)
    try:
        from .tasks import run_automation_task

        run_automation_task.delay(trigger_type, organization.id, task_context)
        logger.info(
            "Queued automation task trigger_type=%s organization_id=%s",
            trigger_type,
            organization.id,
        )
    except Exception as error:
        logger.warning(
            "Celery unavailable; running automation synchronously trigger_type=%s organization_id=%s error=%s",
            trigger_type,
            organization.id,
            error,
        )
        run_automations(trigger_type, organization, context)


def run_automations_on_commit(trigger_type, organization, context):
    transaction.on_commit(lambda: enqueue_automations(trigger_type, organization, context), robust=True)
