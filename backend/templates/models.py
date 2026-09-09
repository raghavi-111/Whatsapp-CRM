from django.conf import settings
from django.db import models

from organizations.models import Organization


class MessageTemplate(models.Model):
    CATEGORY_MARKETING = "marketing"
    CATEGORY_UTILITY = "utility"
    CATEGORY_AUTHENTICATION = "authentication"

    CATEGORY_CHOICES = [
        (CATEGORY_MARKETING, "Marketing"),
        (CATEGORY_UTILITY, "Utility"),
        (CATEGORY_AUTHENTICATION, "Authentication"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_PAUSED = "paused"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_PAUSED, "Paused"),
    ]

    HEADER_NONE = "none"
    HEADER_TEXT = "text"
    HEADER_IMAGE = "image"
    HEADER_DOCUMENT = "document"
    HEADER_VIDEO = "video"

    HEADER_TYPE_CHOICES = [
        (HEADER_NONE, "None"),
        (HEADER_TEXT, "Text"),
        (HEADER_IMAGE, "Image"),
        (HEADER_DOCUMENT, "Document"),
        (HEADER_VIDEO, "Video"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="message_templates",
    )
    name = models.CharField(max_length=255)
    language = models.CharField(max_length=20)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_UTILITY)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    header_type = models.CharField(max_length=20, choices=HEADER_TYPE_CHOICES, default=HEADER_NONE)
    header_text = models.CharField(max_length=255, blank=True)
    body_text = models.TextField()
    footer_text = models.CharField(max_length=255, blank=True)
    buttons_json = models.JSONField(default=list, blank=True)
    meta_template_id = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_message_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name", "language"],
                name="unique_template_name_language_per_org",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.language})"
