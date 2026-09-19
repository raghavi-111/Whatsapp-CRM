from django.contrib import admin

from .models import MessageTemplate


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "language", "organization", "category", "status", "header_type", "updated_at")
    list_filter = ("category", "status", "header_type", "language")
    search_fields = ("name", "body_text", "organization__name", "meta_template_id")
    autocomplete_fields = ["organization", "created_by"]
    readonly_fields = ["created_at", "updated_at"]
