from django.contrib import admin

from .models import AutomationLog, AutomationRule


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "trigger_type", "is_active", "created_by", "created_at")
    list_filter = ("trigger_type", "is_active", "created_at")
    search_fields = ("name", "description", "organization__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AutomationLog)
class AutomationLogAdmin(admin.ModelAdmin):
    list_display = ("rule", "organization", "trigger_type", "status", "created_at")
    list_filter = ("trigger_type", "status", "created_at")
    search_fields = ("rule__name", "message", "organization__name")
    readonly_fields = ("organization", "rule", "trigger_type", "status", "message", "context_json", "created_at")
