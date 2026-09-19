from django.conf import settings
from django.db import models

from organizations.models import Organization


class CustomerFlow(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_CHOICES = [(STATUS_DRAFT, "Draft"), (STATUS_ACTIVE, "Active")]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="customer_flows")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    start_trigger_json = models.JSONField(default=dict)
    steps_json = models.JSONField(default=list)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["organization", "status"])]


class FlowRun(models.Model):
    STATUS_RUNNING = "running"
    STATUS_WAITING = "waiting"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [(STATUS_RUNNING, "Running"), (STATUS_WAITING, "Waiting"), (STATUS_COMPLETED, "Completed"), (STATUS_FAILED, "Failed"), (STATUS_CANCELLED, "Cancelled")]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="flow_runs")
    flow = models.ForeignKey(CustomerFlow, on_delete=models.CASCADE, related_name="runs")
    contact = models.ForeignKey("contacts.Contact", on_delete=models.CASCADE, related_name="flow_runs")
    conversation = models.ForeignKey("conversations.Conversation", on_delete=models.CASCADE, related_name="flow_runs")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING, db_index=True)
    current_step = models.PositiveIntegerField(default=0)
    state_json = models.JSONField(default=dict, blank=True)
    last_inbound_message = models.ForeignKey("conversations.Message", on_delete=models.SET_NULL, null=True, blank=True, related_name="advanced_flow_runs")
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["flow", "contact"], condition=models.Q(status__in=["running", "waiting"]), name="one_active_run_per_flow_contact")]


class FlowLog(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="flow_logs")
    run = models.ForeignKey(FlowRun, on_delete=models.CASCADE, related_name="logs")
    step_index = models.PositiveIntegerField(default=0)
    step_type = models.CharField(max_length=40)
    status = models.CharField(max_length=20)
    message = models.TextField(blank=True)
    whatsapp_message_id = models.CharField(max_length=255, blank=True)
    inbound_message = models.ForeignKey("conversations.Message", on_delete=models.SET_NULL, null=True, blank=True, related_name="flow_logs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["run", "inbound_message"], condition=models.Q(inbound_message__isnull=False), name="flow_run_inbound_once")]
