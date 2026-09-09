from django.contrib import admin

from .models import Deal


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ["title", "organization", "contact", "stage", "status", "value", "source", "created_at"]
    list_filter = ["stage", "status", "source", "created_at"]
    search_fields = ["title", "contact__full_name", "contact__phone_number", "organization__name"]
