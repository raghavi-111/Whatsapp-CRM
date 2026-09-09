from rest_framework import serializers

from conversations.models import Conversation

from .models import AutomationLog, AutomationMedia, AutomationRule, Media


SUPPORTED_ACTION_TYPES = {
    "add_tag",
    "remove_tag",
    "assign_agent",
    "update_conversation_status",
    "send_message",
    "send_template",
    "send_image",
    "send_document",
    "send_brochure",
    "send_video",
    "send_audio",
    "send_media",
    "create_deal",
    "update_deal_stage",
    "create_notification",
    "add_conversation_note",
    "add_contact_note",
    "stop",
}

MEDIA_ACTION_TYPES = {"send_image", "send_document", "send_brochure", "send_video", "send_audio", "send_media"}
MEDIA_TYPE_BY_ACTION = {
    "send_image": "image", "send_document": "document", "send_brochure": "document",
    "send_video": "video", "send_audio": "audio",
}

SUPPORTED_CONDITION_FIELDS = {
    "contact_source",
    "contact_status",
    "message_text_contains",
    "message_text_equals",
    "message_text_starts_with",
    "message_text_ends_with",
    "conversation_status",
    "contact_has_tag",
    "contact_does_not_have_tag",
    "deal_stage",
    "business_hours",
    "assigned_user",
    "first_message",
}

SUPPORTED_CONDITION_OPERATORS = {"equals", "not_equals", "contains", "icontains", "starts_with", "ends_with"}


class AutomationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationRule
        fields = [
            "id",
            "organization",
            "name",
            "description",
            "trigger_type",
            "condition_logic",
            "conditions_json",
            "actions_json",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_by", "created_at", "updated_at"]

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Automation name is required.")
        return value.strip()

    def validate_conditions_json(self, value):
        if value in [None, ""]:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Conditions must be a JSON array.")
        for index, condition in enumerate(value, start=1):
            if not isinstance(condition, dict):
                raise serializers.ValidationError(f"Condition {index} must be an object.")
            field = condition.get("field")
            if field not in SUPPORTED_CONDITION_FIELDS:
                raise serializers.ValidationError(f"Condition {index} has unsupported field: {field}.")
            operator = condition.get("operator", "equals")
            if operator not in SUPPORTED_CONDITION_OPERATORS:
                raise serializers.ValidationError(f"Condition {index} has unsupported operator: {operator}.")
            if field not in {"business_hours", "first_message"} and ("value" not in condition or str(condition.get("value", "")).strip() == ""):
                raise serializers.ValidationError(f"Condition {index} requires value.")
        return value

    def validate_actions_json(self, value):
        if value in [None, ""]:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Actions must be a JSON array.")
        allowed_statuses = [choice[0] for choice in Conversation.STATUS_CHOICES]
        for index, action in enumerate(value, start=1):
            if not isinstance(action, dict):
                raise serializers.ValidationError(f"Action {index} must be an object.")
            action_type = action.get("type")
            if action_type not in SUPPORTED_ACTION_TYPES:
                raise serializers.ValidationError(f"Action {index} has unsupported type: {action_type}.")
            if action_type in {"add_tag", "remove_tag"} and not str(action.get("tag_name", "")).strip():
                raise serializers.ValidationError(f"Action {index} {action_type} requires tag_name.")
            if action_type == "assign_agent" and not (
                action.get("agent_id") or action.get("user_id") or str(action.get("agent_email", "")).strip()
            ):
                raise serializers.ValidationError(
                    f"Action {index} assign_agent requires agent_id, user_id, or agent_email."
                )
            if action_type == "update_conversation_status" and action.get("status") not in allowed_statuses:
                raise serializers.ValidationError(
                    f"Action {index} update_conversation_status requires a valid status."
                )
            if action_type == "send_message" and not str(action.get("text", "")).strip():
                raise serializers.ValidationError(f"Action {index} send_message requires text.")
            if action_type == "send_template":
                has_template_id = bool(action.get("template_id"))
                has_template_name = bool(str(action.get("template_name", "")).strip())
                has_language = bool(str(action.get("language", "")).strip())
                if not has_template_id and not (has_template_name and has_language):
                    raise serializers.ValidationError(
                        f"Action {index} send_template requires template_id or template_name and language."
                    )
                parameters = action.get("parameters", [])
                if parameters and not isinstance(parameters, list):
                    raise serializers.ValidationError(f"Action {index} send_template parameters must be a JSON array.")
            if action_type in MEDIA_ACTION_TYPES:
                if not action.get("media_id") and not str(action.get("file_url", "")).strip():
                    raise serializers.ValidationError(f"Action {index} {action_type} requires media_id or file_url.")
                if action.get("media_id") and str(action.get("file_url", "")).strip():
                    raise serializers.ValidationError(f"Action {index} must use either media_id or file_url, not both.")
                if str(action.get("file_url", "")).strip() and not str(action["file_url"]).lower().startswith("https://"):
                    raise serializers.ValidationError(f"Action {index} file_url must be a public HTTPS URL.")
                expected = MEDIA_TYPE_BY_ACTION.get(action_type)
                supplied = str(action.get("media_type", expected or "")).strip()
                if action_type == "send_media" and supplied not in {"image", "document", "video", "audio"}:
                    raise serializers.ValidationError(f"Action {index} send_media requires a valid media_type.")
                if expected and supplied and supplied != expected:
                    raise serializers.ValidationError(f"Action {index} media type must be {expected}.")
                media_id = action.get("media_id")
                if media_id and not AutomationMedia.objects.filter(id=media_id, organization=self.context["organization"]).exists():
                    raise serializers.ValidationError(f"Action {index} media was not found in this organization.")
                action.pop("media_source", None)
                if media_id:
                    asset = AutomationMedia.objects.get(id=media_id, organization=self.context["organization"])
                    action["filename"] = asset.filename
                    action["mime_type"] = asset.mime_type
                    action["media_type"] = asset.media_type
                    action.pop("file_url", None)
            if action_type in {"add_conversation_note", "add_contact_note"} and not str(action.get("note", "")).strip():
                raise serializers.ValidationError(f"Action {index} {action_type} requires note.")
            if action_type == "update_deal_stage" and not str(action.get("stage", "")).strip():
                raise serializers.ValidationError(f"Action {index} update_deal_stage requires stage.")
            if action_type == "create_notification" and not str(action.get("message", "")).strip():
                raise serializers.ValidationError(f"Action {index} create_notification requires message.")
        return value


class AutomationMediaSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = AutomationMedia
        fields = ["id", "filename", "mime_type", "media_type", "size", "file_url", "created_at"]
        read_only_fields = fields

    def get_file_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class MediaSerializer(serializers.ModelSerializer):
    original_filename = serializers.CharField(source="filename", read_only=True)
    uploaded_by = serializers.IntegerField(source="created_by_id", read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Media
        fields = ["id", "media_type", "original_filename", "uploaded_by", "created_at", "file_url"]
        read_only_fields = fields

    def get_file_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url


class AutomationLogSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)

    class Meta:
        model = AutomationLog
        fields = [
            "id",
            "organization",
            "rule",
            "rule_name",
            "trigger_type",
            "status",
            "message",
            "context_json",
            "matched_conditions_json",
            "actions_executed_json",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields
