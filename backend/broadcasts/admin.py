from django.contrib import admin

from .models import BroadcastCampaign, BroadcastRecipient


class BroadcastRecipientInline(admin.TabularInline):
    model = BroadcastRecipient
    extra = 0
    readonly_fields = ["phone", "status", "whatsapp_message_id", "error_message", "sent_at", "delivered_at", "read_at"]


@admin.register(BroadcastCampaign)
class BroadcastCampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "template", "status", "recipient_count", "sent_count", "failed_count", "created_at"]
    list_filter = ["status", "audience_type", "created_at"]
    search_fields = ["name", "template__name", "organization__name"]
    inlines = [BroadcastRecipientInline]


@admin.register(BroadcastRecipient)
class BroadcastRecipientAdmin(admin.ModelAdmin):
    list_display = ["campaign", "phone", "status", "whatsapp_message_id", "updated_at"]
    list_filter = ["status", "updated_at"]
    search_fields = ["phone", "whatsapp_message_id", "campaign__name"]
