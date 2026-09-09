import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

from organizations.models import Organization


def default_business_providers():
    return ["openstreetmap", "playwright"]


def default_people_providers():
    return ["official_website"]


class ProviderSettings(models.Model):
    OPENSTREETMAP = "openstreetmap"
    GEOAPIFY = "geoapify"
    GOOGLE = "google"
    PLAYWRIGHT = "playwright"
    BUSINESS_PROVIDER_CHOICES = [
        (OPENSTREETMAP, "OpenStreetMap"),
        (GEOAPIFY, "Geoapify"),
        (GOOGLE, "Google Places"),
        (PLAYWRIGHT, "Browser Search"),
    ]
    # Compatibility alias retained for the carefully ported provider layer.
    HOTEL_PROVIDER_CHOICES = BUSINESS_PROVIDER_CHOICES

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="lead_collector_settings"
    )
    hotel_provider = models.CharField(
        max_length=20, choices=BUSINESS_PROVIDER_CHOICES, default=OPENSTREETMAP
    )
    business_providers = models.JSONField(default=default_business_providers)
    people_providers = models.JSONField(default=default_people_providers)
    apollo_enabled = models.BooleanField(default=False)
    google_api_key_encrypted = models.TextField(blank=True)
    geoapify_api_key_encrypted = models.TextField(blank=True)
    apollo_api_key_encrypted = models.TextField(blank=True)
    zoominfo_api_key_encrypted = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def _fernet(self):
        digest = hashlib.sha256(
            f"{settings.SECRET_KEY}:{self.organization_id}".encode("utf-8")
        ).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def _set_secret(self, field, value):
        setattr(self, field, self._fernet().encrypt(value.encode()).decode() if value else "")

    def _get_secret(self, field):
        encrypted = getattr(self, field)
        if not encrypted:
            return ""
        try:
            return self._fernet().decrypt(encrypted.encode()).decode()
        except InvalidToken:
            return ""

    def set_google_api_key(self, value): self._set_secret("google_api_key_encrypted", value)
    def get_google_api_key(self): return self._get_secret("google_api_key_encrypted")
    def set_geoapify_api_key(self, value): self._set_secret("geoapify_api_key_encrypted", value)
    def get_geoapify_api_key(self): return self._get_secret("geoapify_api_key_encrypted")
    def set_apollo_api_key(self, value): self._set_secret("apollo_api_key_encrypted", value)
    def get_apollo_api_key(self): return self._get_secret("apollo_api_key_encrypted")
    def set_zoominfo_api_key(self, value): self._set_secret("zoominfo_api_key_encrypted", value)
    def get_zoominfo_api_key(self): return self._get_secret("zoominfo_api_key_encrypted")


class DiscoverySearch(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETE = "complete"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [(value, value.title()) for value in (
        STATUS_PENDING, STATUS_RUNNING, STATUS_COMPLETE, STATUS_FAILED
    )]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="discovery_searches")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    location_name = models.CharField(max_length=300)
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius_m = models.PositiveIntegerField()
    category = models.CharField(max_length=80)
    providers = models.JSONField(default=list)
    search_depth = models.CharField(max_length=20, default="standard")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    diagnostics = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "-created_at"])]


class DiscoveredBusiness(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="discovered_businesses")
    search = models.ForeignKey(DiscoverySearch, on_delete=models.CASCADE, related_name="businesses")
    identity_key = models.CharField(max_length=500)
    name = models.CharField(max_length=300)
    phone_normalized = models.CharField(max_length=50, blank=True)
    website_domain = models.CharField(max_length=255, blank=True)
    provider_place_id = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(
            fields=["search", "identity_key"], name="unique_business_identity_per_search"
        )]
        indexes = [
            models.Index(fields=["organization", "phone_normalized"]),
            models.Index(fields=["organization", "website_domain"]),
            models.Index(fields=["organization", "provider_place_id"]),
        ]


class LeadImportRecord(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="lead_collector_imports")
    business = models.ForeignKey(DiscoveredBusiness, on_delete=models.PROTECT, related_name="lead_imports")
    lead = models.OneToOneField("leads.Lead", on_delete=models.CASCADE, related_name="collector_import")
    identity_key = models.CharField(max_length=500)
    phone_normalized = models.CharField(max_length=50, blank=True)
    whatsapp_normalized = models.CharField(max_length=50, blank=True)
    website_domain = models.CharField(max_length=255, blank=True)
    provider_place_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["organization", "business"], name="unique_imported_business_per_org"
        )]
        indexes = [
            models.Index(fields=["organization", "phone_normalized"]),
            models.Index(fields=["organization", "whatsapp_normalized"]),
            models.Index(fields=["organization", "website_domain"]),
            models.Index(fields=["organization", "provider_place_id"]),
        ]


class WhatsAppContactImportRecord(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="lead_collector_contact_imports")
    business = models.ForeignKey(DiscoveredBusiness, on_delete=models.PROTECT, related_name="whatsapp_contact_imports", null=True, blank=True)
    contact = models.ForeignKey("contacts.Contact", on_delete=models.CASCADE, related_name="lead_collector_imports")
    normalized_number = models.CharField(max_length=50)
    evidence_type = models.CharField(max_length=100, blank=True)
    evidence_url = models.URLField(blank=True, max_length=1000)
    status = models.CharField(max_length=30, default="CONFIRMED_PUBLIC")
    provider_source = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=30, default="lead_collector")
    workbook_filename = models.CharField(max_length=255, blank=True)
    worksheet_name = models.CharField(max_length=255, blank=True)
    source_row = models.PositiveIntegerField(null=True, blank=True)
    import_key = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "business", "normalized_number"], name="unique_whatsapp_import_evidence_per_org")]
        indexes = [models.Index(fields=["organization", "normalized_number"], name="lead_collec_organiz_65fbad_idx")]
