from django.conf import settings
from django.db import models

from contacts.models import Contact
from organizations.models import Organization
from support.models import Tag
from templates.models import MessageTemplate


class BroadcastCampaign(models.Model):
    AUDIENCE_ALL = "all"
    AUDIENCE_TAGS = "tags"
    AUDIENCE_FILTERS = "filters"

    AUDIENCE_CHOICES = [
        (AUDIENCE_ALL, "All contacts"),
        (AUDIENCE_TAGS, "Contacts by tags"),
        (AUDIENCE_FILTERS, "Contacts by filters"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_SCHEDULED = "scheduled"
    STATUS_QUEUED = "queued"
    STATUS_SENDING = "sending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENDING, "Sending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="broadcast_campaigns")
    name = models.CharField(max_length=255)
    audience_type = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    selected_tags = models.ManyToManyField(Tag, blank=True, related_name="broadcast_campaigns")
    contact_status = models.CharField(max_length=20, blank=True)
    contact_source = models.CharField(max_length=20, blank=True)
    template = models.ForeignKey(MessageTemplate, on_delete=models.PROTECT, related_name="broadcast_campaigns")
    template_language = models.CharField(max_length=20)
    variable_mappings = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    recipient_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    read_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_broadcast_campaigns",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self):
        return self.name


class BroadcastRecipient(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_DELIVERED = "delivered"
    STATUS_READ = "read"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_READ, "Read"),
        (STATUS_FAILED, "Failed"),
    ]

    campaign = models.ForeignKey(BroadcastCampaign, on_delete=models.CASCADE, related_name="recipients")
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="broadcast_recipients")
    phone = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    whatsapp_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["campaign", "contact"], name="unique_broadcast_contact_per_campaign"),
        ]

    def __str__(self):
        return f"{self.campaign_id}: {self.phone}"
