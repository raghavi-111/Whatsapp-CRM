from rest_framework import serializers

from organizations.models import OrganizationMember
from pipelines.models import Deal
from pipelines.serializers import DealSerializer
from whatsapp.sending import WhatsAppSendError, normalize_phone_number

from .models import Lead, Service


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "organization", "name", "code", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Service name is required.")
        return value

    def validate_code(self, value):
        value = value.strip().upper().replace(" ", "_")
        if not value:
            raise serializers.ValidationError("Service code is required.")
        return value

    def validate(self, attrs):
        organization = self.context["organization"]
        for field in ("name", "code"):
            value = attrs.get(field, getattr(self.instance, field, None))
            query = Service.objects.filter(organization=organization, **{f"{field}__iexact": value})
            if self.instance:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise serializers.ValidationError({field: f"A service with this {field} already exists."})
        return attrs


class LeadSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    assigned_to_email = serializers.EmailField(source="assigned_to.email", read_only=True)
    converted_deal_details = DealSerializer(source="converted_deal", read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id", "organization", "contact", "name", "phone", "email", "service", "service_name",
            "source", "status", "assigned_to", "assigned_to_email", "next_follow_up", "notes",
            "converted_deal", "converted_deal_details", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "converted_deal", "converted_deal_details", "created_by", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Lead name is required.")
        return value

    def validate_phone(self, value):
        try:
            return normalize_phone_number(value)
        except WhatsAppSendError as error:
            raise serializers.ValidationError("Phone number is invalid.") from error

    def validate(self, attrs):
        organization = self.context["organization"]
        service = attrs.get("service", getattr(self.instance, "service", None))
        if service and service.organization_id != organization.id:
            raise serializers.ValidationError({"service": "Service must belong to the current organization."})
        contact = attrs.get("contact", getattr(self.instance, "contact", None))
        if contact and contact.organization_id != organization.id:
            raise serializers.ValidationError({"contact": "Contact must belong to the current organization."})
        assigned_to = attrs.get("assigned_to", getattr(self.instance, "assigned_to", None))
        if assigned_to and not OrganizationMember.objects.filter(
            organization=organization, user=assigned_to, status=OrganizationMember.STATUS_ACTIVE
        ).exists():
            raise serializers.ValidationError({"assigned_to": "Assigned user must be an active member of the current organization."})
        requested_status = attrs.get("status")
        if requested_status == Lead.STATUS_CONVERTED and not (self.instance and self.instance.converted_deal_id):
            raise serializers.ValidationError({"status": "Use the convert action to mark a lead as converted."})
        return attrs
