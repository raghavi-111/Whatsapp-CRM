from django.conf import settings
from django.db import models

from organizations.models import Organization


class Tag(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20, default="#128c7e")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_tag_name_per_org")
        ]

    def __str__(self):
        return self.name


class ContactNote(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="contact_notes")
    contact = models.ForeignKey("contacts.Contact", on_delete=models.CASCADE, related_name="contact_notes")
    note = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_contact_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.note[:50]


class ConversationNote(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="conversation_notes")
    conversation = models.ForeignKey("conversations.Conversation", on_delete=models.CASCADE, related_name="conversation_notes")
    note = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_conversation_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.note[:50]
