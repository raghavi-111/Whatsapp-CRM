from rest_framework import serializers

from contacts.models import Contact
from whatsapp.sending import WhatsAppSendError, normalize_phone_number

from .models import Deal


class NewLeadSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=255, trim_whitespace=True)
    phone_number = serializers.CharField(max_length=50, trim_whitespace=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    company = serializers.CharField(max_length=255, required=False, allow_blank=True, trim_whitespace=True)
    notes = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    source = serializers.ChoiceField(choices=Contact.SOURCE_CHOICES, required=False, default=Contact.SOURCE_MANUAL)

    def validate_customer_name(self, value):
        if not value:
            raise serializers.ValidationError("Customer name is required.")
        return value

    def validate_phone_number(self, value):
        try:
            return normalize_phone_number(value)
        except WhatsAppSendError as error:
            raise serializers.ValidationError("Phone number is invalid.") from error


class DealSerializer(serializers.ModelSerializer):
    contact_name = serializers.SerializerMethodField()
    contact_phone_number = serializers.SerializerMethodField()
    new_lead = NewLeadSerializer(write_only=True, required=False)

    class Meta:
        model = Deal
        fields = [
            "id",
            "organization",
            "contact",
            "contact_name",
            "contact_phone_number",
            "new_lead",
            "title",
            "value",
            "stage",
            "status",
            "source",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organization", "contact_name", "contact_phone_number", "created_at", "updated_at"]

    def get_contact_name(self, obj):
        if obj.contact_id is None:
            return ""
        return obj.contact.full_name or obj.contact.phone_number

    def get_contact_phone_number(self, obj):
        return obj.contact.phone_number if obj.contact_id else ""

    def validate_contact(self, value):
        organization = self.context["organization"]
        if value is not None and value.organization_id != organization.id:
            raise serializers.ValidationError("Contact must belong to the current organization.")
        return value

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Deal name is required.")
        return value

    def validate_value(self, value):
        if value < 0:
            raise serializers.ValidationError("Deal value cannot be negative.")
        return value

    def validate(self, attrs):
        organization = self.context["organization"]
        new_lead = attrs.get("new_lead")
        if new_lead is not None and attrs.get("contact") is not None:
            raise serializers.ValidationError("Choose either an existing contact or a new lead.")
        if self.instance is not None and new_lead is not None:
            raise serializers.ValidationError({"new_lead": "New lead details are only accepted when creating a deal."})

        if new_lead is not None:
            contact = Contact.objects.filter(
                organization=organization,
                phone_number=new_lead["phone_number"],
            ).first()
        else:
            contact = attrs.get("contact", getattr(self.instance, "contact", None))
        status = attrs.get("status", getattr(self.instance, "status", Deal.STATUS_OPEN))

        if contact is not None and status == Deal.STATUS_OPEN:
            duplicate_deals = Deal.objects.filter(
                organization=organization,
                contact=contact,
                status=Deal.STATUS_OPEN,
            )
            if self.instance is not None:
                duplicate_deals = duplicate_deals.exclude(id=self.instance.id)
            if duplicate_deals.exists():
                raise serializers.ValidationError(
                    {"contact": "This contact already has an open deal."}
                )

        return attrs

    def create(self, validated_data):
        new_lead = validated_data.pop("new_lead", None)
        if new_lead is not None:
            contact, _ = Contact.objects.get_or_create(
                organization=self.context["organization"],
                phone_number=new_lead["phone_number"],
                defaults={
                    "full_name": new_lead["customer_name"],
                    "email": new_lead.get("email", ""),
                    "company_name": new_lead.get("company", ""),
                    "notes": new_lead.get("notes", ""),
                    "source": new_lead.get("source", Contact.SOURCE_MANUAL),
                    "created_by": self.context.get("request_user"),
                },
            )
            validated_data["contact"] = contact
        self.apply_stage_status_defaults(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self.apply_stage_status_defaults(validated_data)
        return super().update(instance, validated_data)

    def apply_stage_status_defaults(self, validated_data):
        if "stage" not in validated_data or "status" in validated_data:
            return
        if validated_data["stage"] == Deal.STAGE_WON:
            validated_data["status"] = Deal.STATUS_WON
        else:
            validated_data["status"] = Deal.STATUS_OPEN
