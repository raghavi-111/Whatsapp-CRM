from django.conf import settings
from django.db import models

from contacts.models import Contact
from organizations.models import Organization
from pipelines.models import Deal


class Service(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="lead_services")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_service_name_per_org"),
            models.UniqueConstraint(fields=["organization", "code"], name="unique_service_code_per_org"),
        ]

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.code = self.code.strip().upper().replace(" ", "_")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Lead(models.Model):
    SOURCE_WHATSAPP = "whatsapp"
    SOURCE_WEBSITE = "website"
    SOURCE_BLOG = "blog"
    SOURCE_INSTAGRAM = "instagram"
    SOURCE_FACEBOOK = "facebook"
    SOURCE_LINKEDIN = "linkedin"
    SOURCE_QR_CODE = "qr_code"
    SOURCE_MARKETING_TEAM = "marketing_team"
    SOURCE_REFERRAL = "referral"
    SOURCE_EXCEL_IMPORT = "excel_import"
    SOURCE_MANUAL_ENTRY = "manual_entry"
    SOURCE_LEAD_COLLECTOR = "lead_collector"
    SOURCE_OTHER = "other"
    SOURCE_CHOICES = [
        (SOURCE_WHATSAPP, "WhatsApp"), (SOURCE_WEBSITE, "Website"), (SOURCE_BLOG, "Blog"),
        (SOURCE_INSTAGRAM, "Instagram"), (SOURCE_FACEBOOK, "Facebook"), (SOURCE_LINKEDIN, "LinkedIn"),
        (SOURCE_QR_CODE, "QR Code"), (SOURCE_MARKETING_TEAM, "Marketing Team"),
        (SOURCE_REFERRAL, "Referral"), (SOURCE_EXCEL_IMPORT, "Excel Import"),
        (SOURCE_MANUAL_ENTRY, "Manual Entry"), (SOURCE_LEAD_COLLECTOR, "Lead Collector"),
        (SOURCE_OTHER, "Other"),
    ]
    STATUS_NEW = "new"
    STATUS_CONTACTED = "contacted"
    STATUS_INTERESTED = "interested"
    STATUS_CONVERTED = "converted"
    STATUS_LOST = "lost"
    STATUS_CHOICES = [
        (STATUS_NEW, "New"), (STATUS_CONTACTED, "Contacted"), (STATUS_INTERESTED, "Interested"),
        (STATUS_CONVERTED, "Converted"), (STATUS_LOST, "Lost"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="leads")
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    email = models.EmailField(blank=True)
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="leads")
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_MANUAL_ENTRY)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_leads")
    next_follow_up = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    converted_deal = models.ForeignKey(Deal, on_delete=models.SET_NULL, null=True, blank=True, related_name="source_leads")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_leads")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "service"]),
            models.Index(fields=["organization", "assigned_to"]),
            models.Index(fields=["organization", "next_follow_up"]),
        ]

    def __str__(self):
        return self.name
