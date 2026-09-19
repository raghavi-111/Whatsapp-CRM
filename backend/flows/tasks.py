from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import FlowRun
from .services import advance_run, flow_steps


@shared_task(name="flows.resume_delayed_run")
def resume_delayed_run(run_id):
    with transaction.atomic():
        run = FlowRun.objects.select_for_update().filter(id=run_id, status=FlowRun.STATUS_WAITING).first()
        if not run: return {"status": "skipped"}
        steps = flow_steps(run)
        if run.current_step >= len(steps) or steps[run.current_step].get("type") != "delay": return {"status": "skipped"}
        run.current_step += 1; run.status = FlowRun.STATUS_RUNNING
        run.state_json = {key: value for key, value in run.state_json.items() if key != "resume_at"}
        run.save(update_fields=["current_step", "status", "state_json", "updated_at"])
        transaction.on_commit(lambda: advance_run(run))
    return {"status": "resumed", "at": timezone.now().isoformat()}
