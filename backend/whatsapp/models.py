from django.db import models

from organizations.models import Organization


class WhatsAppBusinessConfig(models.Model):
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="whatsapp_config",
    )
    business_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    phone_number_id = models.CharField(max_length=255)
    whatsapp_business_account_id = models.CharField(max_length=255)
    meta_app_id = models.CharField(max_length=255, blank=True)
    meta_app_secret = models.TextField()
    access_token = models.TextField()
    webhook_verify_token = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "WhatsApp Business Config"
        verbose_name_plural = "WhatsApp Business Configs"

    def __str__(self):
        return self.business_name or self.phone_number or str(self.organization)


class InboundDispatchLog(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="inbound_dispatch_logs")
    message = models.ForeignKey("conversations.Message", on_delete=models.CASCADE, related_name="dispatch_logs")
    engine = models.CharField(max_length=20)
    status = models.CharField(max_length=20)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["message", "engine"], name="one_dispatch_per_message_engine")]
