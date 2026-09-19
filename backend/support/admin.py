from django.contrib import admin

from .models import ContactNote, ConversationNote, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "color", "updated_at")
    search_fields = ("name", "organization__name")
    autocomplete_fields = ["organization"]


@admin.register(ContactNote)
class ContactNoteAdmin(admin.ModelAdmin):
    list_display = ("contact", "organization", "created_by", "created_at")
    search_fields = ("note", "contact__full_name", "contact__phone_number")
    autocomplete_fields = ["organization", "contact", "created_by"]


@admin.register(ConversationNote)
class ConversationNoteAdmin(admin.ModelAdmin):
    list_display = ("conversation", "organization", "created_by", "created_at")
    search_fields = ("note", "conversation__contact__full_name", "conversation__contact__phone_number")
    autocomplete_fields = ["organization", "conversation", "created_by"]
