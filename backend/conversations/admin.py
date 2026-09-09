from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("contact", "organization", "channel", "status", "assigned_to", "last_message_at")
    list_filter = ("channel", "status", "organization")
    search_fields = ("contact__full_name", "contact__phone_number", "organization__name")
    autocomplete_fields = ["organization", "contact", "assigned_to"]
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "sender_type", "direction", "message_type", "delivery_status", "created_at")
    list_filter = ("sender_type", "direction", "message_type", "delivery_status")
    search_fields = ("text", "external_message_id", "conversation__contact__phone_number")
    autocomplete_fields = ["organization", "conversation"]
