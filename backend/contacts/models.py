from django.conf import settings
from django.db import models

from organizations.models import Organization


class ContactCategory(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="contact_categories")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["organization", "name"], name="unique_contact_category_per_org")]

    def __str__(self):
        return self.name


class Contact(models.Model):
    STATUS_NEW = "new"
    STATUS_ACTIVE = "active"
    STATUS_BLOCKED = "blocked"

    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_BLOCKED, "Blocked"),
    ]

    SOURCE_MANUAL = "manual"
    SOURCE_WHATSAPP = "whatsapp"
    SOURCE_IMPORT = "import"
    SOURCE_WEBSITE = "website"
    SOURCE_REFERRAL = "referral"
    SOURCE_WALK_IN = "walk_in"
    SOURCE_LEAD_COLLECTOR = "lead_collector"

    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_WHATSAPP, "WhatsApp"),
        (SOURCE_IMPORT, "Import"),
        (SOURCE_WEBSITE, "Website"),
        (SOURCE_REFERRAL, "Referral"),
        (SOURCE_WALK_IN, "Walk-in"),
        (SOURCE_LEAD_COLLECTOR, "Lead Collector"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=50)
    email = models.EmailField(blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    notes = models.TextField(blank=True)
    tags = models.ManyToManyField("support.Tag", blank=True, related_name="contacts")
    category = models.ForeignKey(ContactCategory, on_delete=models.PROTECT, null=True, blank=True, related_name="contacts")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_contacts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "phone_number"],
                name="unique_contact_phone_per_organization",
            )
        ]

    def __str__(self):
        return self.full_name or self.phone_number
