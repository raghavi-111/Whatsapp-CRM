from django.contrib import admin

from .models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone_number", "organization", "source", "status", "created_at")
    list_filter = ("source", "status", "organization")
    search_fields = ("full_name", "phone_number", "email", "company_name", "organization__name")
    autocomplete_fields = ["organization", "created_by"]
