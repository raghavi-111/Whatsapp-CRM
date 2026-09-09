from django.conf import settings
from django.db import models
from django.utils import timezone

from contacts.models import Contact
from organizations.models import Organization


class Conversation(models.Model):
    CHANNEL_WHATSAPP = "whatsapp"

    CHANNEL_CHOICES = [
        (CHANNEL_WHATSAPP, "WhatsApp"),
    ]

    STATUS_OPEN = "open"
    STATUS_PENDING = "pending"
    STATUS_RESOLVED = "resolved"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_PENDING, "Pending"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_CLOSED, "Closed"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="conversations",
        db_index=True,
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, default=CHANNEL_WHATSAPP)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_conversations",
    )
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "last_message_at"]),
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self):
        return f"{self.contact} ({self.channel})"


class Message(models.Model):
    SENDER_CONTACT = "contact"
    SENDER_AGENT = "agent"
    SENDER_SYSTEM = "system"

    SENDER_TYPE_CHOICES = [
        (SENDER_CONTACT, "Contact"),
        (SENDER_AGENT, "Agent"),
        (SENDER_SYSTEM, "System"),
    ]

    DIRECTION_INBOUND = "inbound"
    DIRECTION_OUTBOUND = "outbound"

    DIRECTION_CHOICES = [
        (DIRECTION_INBOUND, "Inbound"),
        (DIRECTION_OUTBOUND, "Outbound"),
    ]

    TYPE_TEXT = "text"
    TYPE_IMAGE = "image"
    TYPE_DOCUMENT = "document"
    TYPE_AUDIO = "audio"
    TYPE_VIDEO = "video"
    TYPE_LOCATION = "location"
    TYPE_TEMPLATE = "template"
    TYPE_SYSTEM = "system"

    MESSAGE_TYPE_CHOICES = [
        (TYPE_TEXT, "Text"),
        (TYPE_IMAGE, "Image"),
        (TYPE_DOCUMENT, "Document"),
        (TYPE_AUDIO, "Audio"),
        (TYPE_VIDEO, "Video"),
        (TYPE_LOCATION, "Location"),
        (TYPE_TEMPLATE, "Template"),
        (TYPE_SYSTEM, "System"),
    ]

    DELIVERY_PENDING = "pending"
    DELIVERY_SENT = "sent"
    DELIVERY_DELIVERED = "delivered"
    DELIVERY_READ = "read"
    DELIVERY_FAILED = "failed"

    DELIVERY_STATUS_CHOICES = [
        (DELIVERY_PENDING, "Pending"),
        (DELIVERY_SENT, "Sent"),
        (DELIVERY_DELIVERED, "Delivered"),
        (DELIVERY_READ, "Read"),
        (DELIVERY_FAILED, "Failed"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
    )
    sender_type = models.CharField(max_length=20, choices=SENDER_TYPE_CHOICES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default=TYPE_TEXT)
    text = models.TextField(blank=True)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    external_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    media_file = models.FileField(upload_to="messages/%Y/%m/%d/", blank=True)
    media_url = models.URLField(blank=True)
    media_mime_type = models.CharField(max_length=120, blank=True)
    media_filename = models.CharField(max_length=255, blank=True)
    media_size = models.PositiveIntegerField(null=True, blank=True)
    meta_media_id = models.CharField(max_length=255, blank=True, db_index=True)
    delivery_status = models.CharField(max_length=20, choices=DELIVERY_STATUS_CHOICES, default=DELIVERY_PENDING)
    sent_at = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["external_message_id"]),
        ]

    def __str__(self):
        return self.text[:50] or f"{self.message_type} message"
