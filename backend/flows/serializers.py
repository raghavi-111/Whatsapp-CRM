from rest_framework import serializers

from .models import CustomerFlow, FlowLog, FlowRun

STEP_TYPES = {"send_text", "send_template", "send_media", "ask_question", "wait_reply", "options", "branch", "add_tag", "remove_tag", "create_deal", "update_deal", "assign_member", "notify_team", "delay", "end"}


class CustomerFlowSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerFlow
        fields = ["id", "name", "description", "status", "start_trigger_json", "steps_json", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        if not value.strip(): raise serializers.ValidationError("Flow name is required.")
        return value.strip()

    def validate_steps_json(self, value):
        if not isinstance(value, list): raise serializers.ValidationError("Flow steps must be an array.")
        for index, step in enumerate(value, 1):
            if not isinstance(step, dict) or step.get("type") not in STEP_TYPES:
                raise serializers.ValidationError(f"Step {index} has an unsupported type.")
            if step.get("type") in {"send_text", "ask_question", "options"} and not str(step.get("text", "")).strip():
                raise serializers.ValidationError(f"Step {index} requires text.")
            if step.get("type") == "branch":
                branches = step.get("branches", [])
                if not isinstance(branches, list):
                    raise serializers.ValidationError(f"Step {index} branches must be an array.")
                configured = [branch for branch in branches if isinstance(branch, dict) and (str(branch.get("value", "")).strip() or branch.get("next_step") not in (None, ""))]
                if not configured:
                    raise serializers.ValidationError(f"Step {index} requires at least one branch.")
                seen_values = set()
                for branch_index, branch in enumerate(configured, 1):
                    match_value = str(branch.get("value", "")).strip().casefold()
                    if not match_value:
                        raise serializers.ValidationError(f"Step {index}, branch {branch_index} requires a reply value.")
                    if match_value in seen_values:
                        raise serializers.ValidationError(f"Step {index} has duplicate branch reply values.")
                    seen_values.add(match_value)
                    target = branch.get("next_step")
                    if isinstance(target, bool) or not isinstance(target, int) or not 1 <= target <= len(value):
                        raise serializers.ValidationError(
                            f"Step {index}, branch {branch_index} target must be a UI step number between 1 and {len(value)}."
                        )
        return value


class FlowRunSerializer(serializers.ModelSerializer):
    flow_name = serializers.CharField(source="flow.name", read_only=True)
    contact_name = serializers.CharField(source="contact.full_name", read_only=True)
    contact_phone = serializers.CharField(source="contact.phone_number", read_only=True)
    is_legacy = serializers.SerializerMethodField()

    def get_is_legacy(self, obj):
        return not isinstance((obj.state_json or {}).get("steps_snapshot"), list)

    class Meta:
        model = FlowRun
        fields = ["id", "flow", "flow_name", "contact", "contact_name", "contact_phone", "conversation", "status", "current_step", "state_json", "is_legacy", "started_at", "updated_at", "completed_at"]


class FlowLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowLog
        fields = ["id", "run", "step_index", "step_type", "status", "message", "whatsapp_message_id", "created_at"]
