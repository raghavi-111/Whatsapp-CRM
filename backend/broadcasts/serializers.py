from django.utils import timezone
from rest_framework import serializers

from support.models import Tag
from templates.models import MessageTemplate

from .models import BroadcastCampaign, BroadcastRecipient
from .services import estimate_recipients, extract_template_variables


class BroadcastRecipientSerializer(serializers.ModelSerializer):
    contact_name = serializers.SerializerMethodField()

    class Meta:
        model = BroadcastRecipient
        fields = [
            "id",
            "contact",
            "contact_name",
            "phone",
            "status",
            "whatsapp_message_id",
            "error_message",
            "sent_at",
            "delivered_at",
            "read_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_contact_name(self, obj):
        return obj.contact.full_name if obj.contact_id and obj.contact.full_name else (obj.phone or "")


class BroadcastCampaignSerializer(serializers.ModelSerializer):
    selected_tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.none(),
        many=True,
        source="selected_tags",
        required=False,
    )
    template_name = serializers.CharField(source="template.name", read_only=True)
    template_category = serializers.CharField(source="template.category", read_only=True)
    template_body = serializers.CharField(source="template.body_text", read_only=True)
    template_variables = serializers.SerializerMethodField()
    audience_summary = serializers.SerializerMethodField()
    recipients = BroadcastRecipientSerializer(many=True, read_only=True)

    class Meta:
        model = BroadcastCampaign
        fields = [
            "id",
            "organization",
            "name",
            "audience_type",
            "selected_tag_ids",
            "contact_status",
            "contact_source",
            "template",
            "template_name",
            "template_category",
            "template_language",
            "template_body",
            "template_variables",
            "variable_mappings",
            "status",
            "scheduled_at",
            "recipient_count",
            "sent_count",
            "delivered_count",
            "read_count",
            "failed_count",
            "audience_summary",
            "recipients",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "status",
            "recipient_count",
            "sent_count",
            "delivered_count",
            "read_count",
            "failed_count",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organization = self.context.get("organization")
        if organization is not None:
            self.fields["selected_tag_ids"].child_relation.queryset = Tag.objects.filter(organization=organization)
            self.fields["template"].queryset = MessageTemplate.objects.filter(organization=organization)

    def get_template_variables(self, obj):
        return extract_template_variables(obj.template)

    def get_audience_summary(self, obj):
        if obj.audience_type == BroadcastCampaign.AUDIENCE_ALL:
            return "All contacts"
        if obj.audience_type == BroadcastCampaign.AUDIENCE_TAGS:
            names = list(obj.selected_tags.values_list("name", flat=True))
            return f"Tags: {', '.join(names) if names else 'none'}"
        filters = []
        if obj.contact_status:
            filters.append(f"status={obj.contact_status}")
        if obj.contact_source:
            filters.append(f"source={obj.contact_source}")
        return "Filters: " + (", ".join(filters) if filters else "none")

    def validate_template(self, value):
        organization = self.context["organization"]
        if value.organization_id != organization.id:
            raise serializers.ValidationError("Template must belong to the current organization.")
        if value.status != MessageTemplate.STATUS_APPROVED:
            raise serializers.ValidationError("Only approved templates can be used for broadcasts.")
        return value

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Campaign name is required.")
        return value

    def validate_variable_mappings(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Variable mappings must be a list.")
        for mapping in value:
            if mapping.get("type") not in {"contact_name", "phone_number", "company", "static"}:
                raise serializers.ValidationError("Unsupported variable mapping type.")
        return value

    def validate(self, attrs):
        instance = self.instance
        if instance and instance.status != BroadcastCampaign.STATUS_DRAFT:
            editable_fields = {"name", "audience_type", "selected_tags", "contact_status", "contact_source", "template", "template_language", "variable_mappings", "scheduled_at"}
            if any(field in attrs for field in editable_fields):
                raise serializers.ValidationError("Only draft campaigns can be edited.")

        template = attrs.get("template", getattr(instance, "template", None))
        mappings = attrs.get("variable_mappings", getattr(instance, "variable_mappings", []))
        if template is not None and len(mappings or []) < len(extract_template_variables(template)):
            raise serializers.ValidationError({"variable_mappings": "Map every template variable before saving."})

        audience_type = attrs.get("audience_type", getattr(instance, "audience_type", BroadcastCampaign.AUDIENCE_ALL))
        selected_tags = attrs.get("selected_tags", getattr(instance, "selected_tags", []))
        if audience_type == BroadcastCampaign.AUDIENCE_TAGS and not selected_tags:
            raise serializers.ValidationError({"selected_tag_ids": "Select at least one tag."})

        return attrs

    def create(self, validated_data):
        tags = validated_data.pop("selected_tags", [])
        campaign = super().create(validated_data)
        campaign.selected_tags.set(tags)
        campaign.recipient_count = estimate_recipients(
            campaign.organization,
            campaign.audience_type,
            selected_tags=tags,
            contact_status=campaign.contact_status,
            contact_source=campaign.contact_source,
        )
        campaign.save(update_fields=["recipient_count", "updated_at"])
        return campaign

    def update(self, instance, validated_data):
        tags = validated_data.pop("selected_tags", None)
        campaign = super().update(instance, validated_data)
        if tags is not None:
            campaign.selected_tags.set(tags)
        campaign.recipient_count = estimate_recipients(
            campaign.organization,
            campaign.audience_type,
            selected_tags=campaign.selected_tags.all(),
            contact_status=campaign.contact_status,
            contact_source=campaign.contact_source,
        )
        campaign.save(update_fields=["recipient_count", "updated_at"])
        return campaign


class BroadcastEstimateSerializer(serializers.Serializer):
    audience_type = serializers.ChoiceField(choices=BroadcastCampaign.AUDIENCE_CHOICES)
    selected_tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    contact_status = serializers.CharField(required=False, allow_blank=True)
    contact_source = serializers.CharField(required=False, allow_blank=True)

    def validate_selected_tag_ids(self, value):
        organization = self.context["organization"]
        found = Tag.objects.filter(id__in=value, organization=organization).count()
        if found != len(set(value)):
            raise serializers.ValidationError("One or more tags were not found.")
        return value


class BroadcastScheduleSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()

    def validate_scheduled_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Schedule time must be in the future.")
        return value
