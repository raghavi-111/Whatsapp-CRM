from django.conf import settings
from django.db import models

from organizations.models import Organization


class AutomationRule(models.Model):
    TRIGGER_INBOUND_MESSAGE_RECEIVED = "inbound_message_received"
    TRIGGER_CONVERSATION_CREATED = "conversation_created"
    TRIGGER_CONTACT_CREATED = "contact_created"
    TRIGGER_TAG_ADDED = "tag_added"
    TRIGGER_CONVERSATION_STATUS_CHANGED = "conversation_status_changed"
    TRIGGER_DEAL_CREATED = "deal_created"
    TRIGGER_DEAL_STAGE_CHANGED = "deal_stage_changed"
    TRIGGER_BROADCAST_COMPLETED = "broadcast_completed"

    TRIGGER_CHOICES = [
        (TRIGGER_INBOUND_MESSAGE_RECEIVED, "Inbound message received"),
        (TRIGGER_CONVERSATION_CREATED, "Conversation created"),
        (TRIGGER_CONTACT_CREATED, "Contact created"),
        (TRIGGER_TAG_ADDED, "Tag added"),
        (TRIGGER_CONVERSATION_STATUS_CHANGED, "Conversation status changed"),
        (TRIGGER_DEAL_CREATED, "Deal created"),
        (TRIGGER_DEAL_STAGE_CHANGED, "Deal stage changed"),
        (TRIGGER_BROADCAST_COMPLETED, "Broadcast completed"),
    ]

    CONDITION_LOGIC_AND = "and"
    CONDITION_LOGIC_OR = "or"

    CONDITION_LOGIC_CHOICES = [
        (CONDITION_LOGIC_AND, "AND"),
        (CONDITION_LOGIC_OR, "OR"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="automation_rules")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    trigger_type = models.CharField(max_length=60, choices=TRIGGER_CHOICES, db_index=True)
    condition_logic = models.CharField(max_length=10, choices=CONDITION_LOGIC_CHOICES, default=CONDITION_LOGIC_AND)
    conditions_json = models.JSONField(default=list, blank=True)
    actions_json = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_automation_rules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["organization", "trigger_type", "is_active"]),
        ]

    def __str__(self):
        return self.name


class AutomationMedia(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="automation_media")
    file = models.FileField(upload_to="automation-media/%Y/%m/%d/")
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=150)
    media_type = models.CharField(max_length=20)
    size = models.PositiveBigIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "media_type"])]

    def __str__(self):
        return self.filename

    # Generic media-library naming, while retaining the legacy automation fields.
    @property
    def original_filename(self):
        return self.filename

    @property
    def uploaded_by(self):
        return self.created_by


class Media(AutomationMedia):
    """Reusable view of the existing media table; IDs remain backward compatible."""

    class Meta:
        proxy = True
        verbose_name_plural = "media"


class AutomationLog(models.Model):
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"

    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="automation_logs")
    rule = models.ForeignKey(
        AutomationRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    trigger_type = models.CharField(max_length=60, choices=AutomationRule.TRIGGER_CHOICES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    message = models.TextField(blank=True)
    context_json = models.JSONField(default=dict, blank=True)
    matched_conditions_json = models.JSONField(default=list, blank=True)
    actions_executed_json = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self):
        rule_name = self.rule.name if self.rule else "Deleted rule"
        return f"{rule_name}: {self.status}"
