import logging

from automations.models import AutomationRule
from automations.services import enqueue_automations, run_automations
from flows.models import CustomerFlow, FlowRun
from flows.services import trigger_flows_for_inbound
from .models import InboundDispatchLog
from .sending import force_whatsapp_send_mode

logger = logging.getLogger(__name__)


def dispatch_inbound_consumers(organization, contact, conversation, message, simulation=False):
    results = {}
    if InboundDispatchLog.objects.filter(message=message, engine="automation").exists():
        results["automation"] = "skipped"
    else:
        try:
            active = AutomationRule.objects.filter(organization=organization, trigger_type=AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED, is_active=True).exists()
            if active:
                context = {"contact": contact, "conversation": conversation, "message": message, "message_text": message.text}
                if simulation:
                    with force_whatsapp_send_mode("mock"):
                        run_automations(AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED, organization, context)
                else:
                    enqueue_automations(AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED, organization, context)
                results["automation"] = "dispatched"
            else:
                results["automation"] = "skipped"
            _record(organization, message, "automation", results["automation"], "Active automation dispatch attempted." if active else "No active inbound automations.")
        except Exception as error:
            logger.exception("Automation dispatch failed organization_id=%s message_id=%s", organization.id, message.id)
            results["automation"] = "failed"
            _record(organization, message, "automation", "failed", str(error)[:1000])

    if InboundDispatchLog.objects.filter(message=message, engine="flow").exists():
        results["flow"] = "skipped"
    else:
        try:
            waiting = FlowRun.objects.filter(organization=organization, contact=contact, conversation=conversation, status=FlowRun.STATUS_WAITING, flow__status=CustomerFlow.STATUS_ACTIVE).exists()
            active = CustomerFlow.objects.filter(organization=organization, status=CustomerFlow.STATUS_ACTIVE).exists()
            if waiting or active:
                if simulation:
                    with force_whatsapp_send_mode("mock"):
                        outcome = trigger_flows_for_inbound(organization, contact, conversation, message) or {"status": "skipped"}
                else:
                    outcome = trigger_flows_for_inbound(organization, contact, conversation, message) or {"status": "skipped"}
                results["flow"] = outcome.get("status", "dispatched")
            else:
                results["flow"] = "skipped"
            log_status = results["flow"] if results["flow"] in {"skipped", "failed"} else "dispatched"
            _record(organization, message, "flow", log_status, f"Flow outcome: {results['flow']}.")
        except Exception as error:
            logger.exception("Flow dispatch failed organization_id=%s message_id=%s", organization.id, message.id)
            results["flow"] = "failed"
            _record(organization, message, "flow", "failed", str(error)[:1000])
    return results


def _record(organization, message, engine, status, detail):
    try:
        InboundDispatchLog.objects.update_or_create(message=message, engine=engine, defaults={"organization": organization, "status": status, "detail": detail})
    except Exception:
        logger.exception("Unable to persist inbound dispatch log engine=%s message_id=%s", engine, message.id)
