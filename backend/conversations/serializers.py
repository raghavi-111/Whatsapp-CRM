from rest_framework import serializers

from contacts.models import Contact
from organizations.models import OrganizationMember

from .models import Conversation, Message


class ConversationSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source="contact.full_name", read_only=True)
    contact_phone = serializers.CharField(source="contact.phone_number", read_only=True)
    contact_email = serializers.EmailField(source="contact.email", read_only=True)
    contact_company = serializers.CharField(source="contact.company_name", read_only=True)
    contact_tags = serializers.SerializerMethodField()
    assigned_to_email = serializers.EmailField(source="assigned_to.email", read_only=True)
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "organization",
            "contact",
            "contact_name",
            "contact_phone",
            "contact_email",
            "contact_company",
            "contact_tags",
            "channel",
            "status",
            "assigned_to",
            "assigned_to_email",
            "last_message_preview",
            "last_message_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organization", "last_message_at", "created_at", "updated_at"]

    def get_last_message_preview(self, obj):
        message = obj.messages.order_by("-created_at").first()
        if message is None:
            return ""
        return message.text or message.message_type

    def get_contact_tags(self, obj):
        return [
            {"id": tag.id, "name": tag.name, "color": tag.color}
            for tag in obj.contact.tags.all()
        ]

    def validate_contact(self, contact):
        organization = self.context["organization"]
        if contact.organization_id != organization.id:
            raise serializers.ValidationError("Contact must belong to the current organization.")
        return contact

    def validate_assigned_to(self, user):
        if user is None:
            return user

        organization = self.context["organization"]
        is_active_member = OrganizationMember.objects.filter(
            organization=organization,
            user=user,
            status=OrganizationMember.STATUS_ACTIVE,
        ).exists()

        if not is_active_member:
            raise serializers.ValidationError("Assigned agent must be an active organization member.")

        return user

    def validate(self, attrs):
        organization = self.context["organization"]
        contact = attrs.get("contact", getattr(self.instance, "contact", None))

        if contact is not None and contact.organization_id != organization.id:
            raise serializers.ValidationError({"contact": "Contact must belong to the current organization."})

        return attrs


class MessageSerializer(serializers.ModelSerializer):
    media_file_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "organization",
            "conversation",
            "sender_type",
            "message_type",
            "text",
            "direction",
            "external_message_id",
            "media_file",
            "media_file_url",
            "media_url",
            "media_mime_type",
            "media_filename",
            "media_size",
            "meta_media_id",
            "delivery_status",
            "sent_at",
            "delivered_at",
            "read_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "conversation",
            "media_file_url",
            "created_at",
        ]

    def get_media_file_url(self, obj):
        if not obj.media_file:
            return ""

        request = self.context.get("request")
        url = obj.media_file.url
        return request.build_absolute_uri(url) if request else url

    def validate(self, attrs):
        conversation = self.context["conversation"]
        organization = self.context["organization"]

        if conversation.organization_id != organization.id:
            raise serializers.ValidationError("Conversation must belong to the current organization.")

        message_type = attrs.get("message_type", Message.TYPE_TEXT)
        text = attrs.get("text", "")

        if message_type == Message.TYPE_TEXT and not text.strip():
            raise serializers.ValidationError({"text": "Text is required for text messages."})

        return attrs
