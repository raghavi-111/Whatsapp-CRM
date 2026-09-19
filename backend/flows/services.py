import logging
from copy import deepcopy
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from automations.services import execute_actions
from .models import CustomerFlow, FlowLog, FlowRun


logger = logging.getLogger(__name__)
DEFAULT_UNMATCHED_REPLY = "Please reply with 1, 2, or 3."


def trigger_flows_for_inbound(organization, contact, conversation, message):
    if FlowLog.objects.filter(organization=organization, inbound_message=message).exists():
        return {"status": "skipped", "reason": "duplicate_message"}
    with transaction.atomic():
        waiting_run = (
            FlowRun.objects.select_for_update()
            .select_related("flow")
            .filter(
                organization=organization,
                contact=contact,
                conversation=conversation,
                status=FlowRun.STATUS_WAITING,
                flow__status=CustomerFlow.STATUS_ACTIVE,
            )
            .order_by("-updated_at", "-id")
            .first()
        )
        matching_flows = list(_matching_active_flows(organization, message.text or ""))
        if waiting_run is not None:
            restart_flow = next((flow for flow in matching_flows if flow.id == waiting_run.flow_id), None)
            if restart_flow is not None:
                _cancel_run(waiting_run, "Restarted by matching inbound start trigger.", inbound_message=message)
                new_run = _start_flow(restart_flow, contact, conversation, message, restart_of=waiting_run)
                logger.info(
                    "Flow restarted from inbound trigger old_run_id=%s new_run_id=%s organization_id=%s contact_id=%s message_id=%s",
                    waiting_run.id, new_run.id if new_run else None, organization.id, contact.id, message.id,
                )
                return {"status": "restarted", "run_ids": [new_run.id] if new_run else [], "previous_run_id": waiting_run.id}
            _consume_inbound(waiting_run, message)
            return {"status": "resumed", "run_ids": [waiting_run.id]}

        started = []
        for flow in matching_flows:
            run = _start_flow(flow, contact, conversation, message)
            if run is not None:
                started.append(run.id)
        return {"status": "started" if started else "skipped", "run_ids": started}


def _matching_active_flows(organization, text):
    normalized_text = normalize_reply(text)
    flows = CustomerFlow.objects.filter(organization=organization, status=CustomerFlow.STATUS_ACTIVE).order_by("id")
    matched_ids = []
    for flow in flows:
        trigger = flow.start_trigger_json or {}
        keyword = normalize_reply(trigger.get("value", ""))
        match_type = trigger.get("type", "message_contains")
        matched = not keyword or (keyword in normalized_text if match_type == "message_contains" else keyword == normalized_text)
        if matched:
            matched_ids.append(flow.id)
    return flows.filter(id__in=matched_ids)


def _start_flow(flow, contact, conversation, message=None, restart_of=None):
    try:
        run = FlowRun.objects.create(
            organization=flow.organization,
            flow=flow,
            contact=contact,
            conversation=conversation,
            last_inbound_message=message,
            state_json={"steps_snapshot": deepcopy(flow.steps_json or [])},
        )
    except IntegrityError:
        logger.info("Active flow run already exists flow_id=%s contact_id=%s", flow.id, contact.id)
        return None
    detail = f"Flow restarted from run {restart_of.id}." if restart_of else "Flow started."
    FlowLog.objects.create(
        organization=flow.organization,
        run=run,
        step_type="restart" if restart_of else "start",
        status="success",
        message=detail,
        inbound_message=message,
    )
    advance_run(run, message)
    return run


def _cancel_run(run, reason, inbound_message=None):
    run.status = FlowRun.STATUS_CANCELLED
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "completed_at", "updated_at"])
    FlowLog.objects.create(
        organization=run.organization,
        run=run,
        step_index=run.current_step,
        step_type="restart" if inbound_message else "cancel",
        status="cancelled",
        message=reason,
        inbound_message=inbound_message,
    )


def cancel_flow_run(run_id, organization, reason="Cancelled by operator."):
    with transaction.atomic():
        run = FlowRun.objects.select_for_update().filter(id=run_id, organization=organization).first()
        if run is None:
            return None
        if run.status in {FlowRun.STATUS_RUNNING, FlowRun.STATUS_WAITING}:
            _cancel_run(run, reason)
        return run


def restart_flow_run(run_id, organization):
    with transaction.atomic():
        run = (
            FlowRun.objects.select_for_update()
            .select_related("flow", "contact", "conversation")
            .filter(id=run_id, organization=organization)
            .first()
        )
        if run is None:
            return None, None
        if run.status in {FlowRun.STATUS_RUNNING, FlowRun.STATUS_WAITING}:
            _cancel_run(run, "Restarted by operator.")
        new_run = _start_flow(run.flow, run.contact, run.conversation, restart_of=run)
        return run, new_run


def _consume_inbound(run, message):
    step_before = run.current_step
    received_reply = str(message.text or "")
    normalized_reply = normalize_reply(received_reply)
    try:
        FlowLog.objects.create(organization=run.organization, run=run, step_index=run.current_step, step_type="inbound_reply", status="success", message=(message.text or "")[:500], inbound_message=message)
    except IntegrityError:
        logger.info("Skipping duplicate flow reply run_id=%s message_id=%s", run.id, message.id)
        return
    run.last_inbound_message = message
    if run.status == FlowRun.STATUS_WAITING:
        step = _step(run)
        if step and step.get("type") == "delay":
            resume_at = run.state_json.get("resume_at")
            if resume_at and timezone.now() < datetime.fromisoformat(resume_at):
                run.save(update_fields=["last_inbound_message", "updated_at"])
                return
        if step and step.get("type") == "wait_reply":
            run.current_step += 1
        run.status = FlowRun.STATUS_RUNNING

        branch = _step(run)
        if branch and branch.get("type") == "branch":
            matched_branch, target = branch_target(branch, received_reply)
            branches_evaluated = [
                {"value": item.get("value"), "next_step": item.get("next_step")}
                for item in branch.get("branches", [])
                if isinstance(item, dict)
            ]
            if matched_branch is None:
                _handle_unmatched_branch(run, branch, message, normalized_reply, branches_evaluated)
                logger.info(
                    "Flow branch unmatched run_id=%s current_step_before=%s branch_step=%s received_reply=%r normalized_reply=%r branches=%s resulting_status=%s",
                    run.id, step_before, run.current_step, received_reply, normalized_reply, branches_evaluated, run.status,
                )
                return
            run.current_step = target
            logger.info(
                "Flow branch matched run_id=%s current_step_before=%s received_reply=%r normalized_reply=%r branches=%s matched_branch=%s target_step_ui=%s target_step_internal=%s",
                run.id, step_before, received_reply, normalized_reply, branches_evaluated,
                matched_branch.get("value"), matched_branch.get("next_step"), target,
            )
    run.save(update_fields=["current_step", "status", "last_inbound_message", "updated_at"])
    try:
        advance_run(run, message)
    except Exception:
        logger.exception(
            "Flow resume failed run_id=%s current_step_before=%s received_reply=%r normalized_reply=%r",
            run.id, step_before, received_reply, normalized_reply,
        )
        raise
    logger.info(
        "Flow resume completed run_id=%s current_step_before=%s current_step_after=%s received_reply=%r normalized_reply=%r resulting_status=%s",
        run.id, step_before, run.current_step, received_reply, normalized_reply, run.status,
    )


def _step(run):
    steps = flow_steps(run)
    return steps[run.current_step] if run.current_step < len(steps) else None


def flow_steps(run):
    snapshot = (run.state_json or {}).get("steps_snapshot")
    return snapshot if isinstance(snapshot, list) else (run.flow.steps_json or [])


def normalize_reply(reply):
    return str(reply).strip().casefold()


def branch_target(step, reply):
    normalized_reply = normalize_reply(reply)
    for branch in step.get("branches", []):
        if not isinstance(branch, dict):
            continue
        if normalize_reply(branch.get("value", "")) == normalized_reply:
            # FlowBuilder stores one-based UI step numbers; execution is zero-based.
            return branch, int(branch["next_step"]) - 1
    return None, None


def _handle_unmatched_branch(run, step, message, normalized_reply, branches_evaluated):
    validation_reply = str(step.get("unmatched_reply") or DEFAULT_UNMATCHED_REPLY).strip()
    error_detail = ""
    if validation_reply:
        try:
            execute_actions(
                [{"type": "send_message", "text": validation_reply}],
                run.organization,
                {"contact": run.contact, "conversation": run.conversation, "message": message},
            )
        except Exception as error:
            error_detail = f" Validation reply failed: {error}"
            logger.exception("Unable to send unmatched branch reply run_id=%s", run.id)
    run.status = FlowRun.STATUS_WAITING
    run.save(update_fields=["current_step", "status", "last_inbound_message", "updated_at"])
    FlowLog.objects.create(
        organization=run.organization,
        run=run,
        step_index=run.current_step,
        step_type="branch",
        status="waiting",
        message=f"No branch matched normalized reply {normalized_reply!r}; evaluated {branches_evaluated}.{error_detail}"[:1000],
    )


def action_for_step(step):
    kind = step.get("type")
    mapping = {
        "send_text": {"type": "send_message", "text": step.get("text", "")},
        "ask_question": {"type": "send_message", "text": step.get("text", "")},
        "options": {"type": "send_message", "text": step.get("text", "")},
        "send_template": {"type": "send_template", "template_id": step.get("template_id"), "parameter_mappings": step.get("parameter_mappings", [])},
        "send_media": {"type": "send_media", "media_type": step.get("media_type"), "media_id": step.get("media_id"), "file_url": step.get("file_url", ""), "caption": step.get("caption", ""), "filename": step.get("filename", "")},
        "add_tag": {"type": "add_tag", "tag_name": step.get("tag_name", "")},
        "remove_tag": {"type": "remove_tag", "tag_name": step.get("tag_name", "")},
        "create_deal": {"type": "create_deal", "stage": step.get("stage", "New")},
        "update_deal": {"type": "update_deal_stage", "stage": step.get("stage", "Qualified")},
        "assign_member": {"type": "assign_agent", "agent_id": step.get("agent_id")},
        "notify_team": {"type": "create_notification", "message": step.get("message", "")},
    }
    return mapping.get(kind)


def advance_run(run, inbound_message=None):
    while run.status == FlowRun.STATUS_RUNNING:
        step = _step(run)
        if step is None or step.get("type") == "end":
            run.status, run.completed_at = FlowRun.STATUS_COMPLETED, timezone.now()
            FlowLog.objects.create(organization=run.organization, run=run, step_index=run.current_step, step_type="end", status="success", message="Flow completed.")
            break
        kind = step.get("type")
        if kind in {"wait_reply", "branch"}:
            run.status = FlowRun.STATUS_WAITING
            FlowLog.objects.create(organization=run.organization, run=run, step_index=run.current_step, step_type=kind, status="waiting", message="Waiting for customer reply.")
            break
        if kind == "delay":
            seconds = max(0, min(int(step.get("seconds", 0) or 0), 604800))
            run.state_json = {**run.state_json, "resume_at": (timezone.now() + timedelta(seconds=seconds)).isoformat()}
            run.status = FlowRun.STATUS_WAITING
            FlowLog.objects.create(organization=run.organization, run=run, step_index=run.current_step, step_type=kind, status="waiting", message=f"Waiting {seconds} seconds.")
            run.save(update_fields=["status", "state_json", "updated_at"])
            from .tasks import resume_delayed_run
            transaction.on_commit(lambda run_id=run.id, countdown=seconds: resume_delayed_run.apply_async(args=[run_id], countdown=countdown))
            break
        try:
            action = action_for_step(step)
            if action:
                results = execute_actions([action], run.organization, {"contact": run.contact, "conversation": run.conversation, "message": inbound_message})
                wamid = results[0].get("whatsapp_message_id", "") if results else ""
            else: wamid = ""
            FlowLog.objects.create(organization=run.organization, run=run, step_index=run.current_step, step_type=kind, status="success", whatsapp_message_id=wamid)
            run.current_step += 1
        except Exception as error:
            run.status = FlowRun.STATUS_FAILED
            FlowLog.objects.create(organization=run.organization, run=run, step_index=run.current_step, step_type=kind, status="failed", message=str(error)[:1000])
    run.save(update_fields=["current_step", "status", "state_json", "completed_at", "updated_at"])
