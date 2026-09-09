from django.contrib import admin

from .models import WhatsAppBusinessConfig


@admin.register(WhatsAppBusinessConfig)
class WhatsAppBusinessConfigAdmin(admin.ModelAdmin):
    list_display = ("organization", "business_name", "phone_number", "phone_number_id", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = (
        "organization__name",
        "business_name",
        "phone_number",
        "phone_number_id",
        "whatsapp_business_account_id",
    )
    autocomplete_fields = ["organization"]
    readonly_fields = ["created_at", "updated_at"]
