import re

from rest_framework import serializers

from contacts.models import Contact
from conversations.models import Conversation
from .models import MessageTemplate


class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = [
            "id",
            "organization",
            "name",
            "language",
            "category",
            "status",
            "header_type",
            "header_text",
            "body_text",
            "footer_text",
            "buttons_json",
            "meta_template_id",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_by", "created_at", "updated_at"]

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Template name is required.")
        return value.strip()

    def validate_language(self, value):
        if not value.strip():
            raise serializers.ValidationError("Language is required.")
        return value.strip().lower()

    def validate_body_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Body text is required.")
        return value

    def validate(self, attrs):
        organization = self.context["organization"]
        name = attrs.get("name", getattr(self.instance, "name", "")).strip()
        language = attrs.get("language", getattr(self.instance, "language", "")).strip().lower()

        duplicate_templates = MessageTemplate.objects.filter(
            organization=organization,
            name=name,
            language=language,
        )

        if self.instance is not None:
            duplicate_templates = duplicate_templates.exclude(id=self.instance.id)

        if duplicate_templates.exists():
            raise serializers.ValidationError(
                {"name": "A template with this name and language already exists in this organization."}
            )

        return attrs


class SendTemplateSerializer(serializers.Serializer):
    contact_id = serializers.IntegerField(required=True)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    parameters = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        allow_empty=True,
    )

    def validate_contact_id(self, value):
        organization = self.context["organization"]
        if not Contact.objects.filter(id=value, organization=organization).exists():
            raise serializers.ValidationError("Contact not found in current organization.")
        return value

    def validate_conversation_id(self, value):
        if value is None:
            return value

        organization = self.context["organization"]
        if not Conversation.objects.filter(id=value, organization=organization).exists():
            raise serializers.ValidationError("Conversation not found in current organization.")
        return value

    def validate(self, attrs):
        template = self.context["template"]
        parameter_indexes = {int(value) for value in re.findall(r"{{\s*(\d+)\s*}}", template.body_text)}
        expected_count = max(parameter_indexes, default=0)
        parameters = attrs.get("parameters", [])
        if len(parameters) != expected_count:
            raise serializers.ValidationError(
                {"parameters": f"This template requires exactly {expected_count} parameter(s)."}
            )
        return attrs
