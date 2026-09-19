from rest_framework import serializers

from .models import WhatsAppBusinessConfig


SENSITIVE_FIELDS = ["meta_app_secret", "access_token", "webhook_verify_token"]


def mask_secret(value):
    if not value:
        return ""

    if len(value) <= 4:
        return "****"

    return f"****{value[-4:]}"


class WhatsAppBusinessConfigSerializer(serializers.ModelSerializer):
    meta_app_secret = serializers.CharField(required=False, allow_blank=True, write_only=True)
    access_token = serializers.CharField(required=False, allow_blank=True, write_only=True)
    webhook_verify_token = serializers.CharField(required=False, allow_blank=True, write_only=True)
    meta_app_secret_masked = serializers.SerializerMethodField()
    access_token_masked = serializers.SerializerMethodField()
    webhook_verify_token_masked = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppBusinessConfig
        fields = [
            "id",
            "organization",
            "business_name",
            "phone_number",
            "phone_number_id",
            "whatsapp_business_account_id",
            "meta_app_id",
            "meta_app_secret",
            "access_token",
            "webhook_verify_token",
            "meta_app_secret_masked",
            "access_token_masked",
            "webhook_verify_token_masked",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "meta_app_secret_masked",
            "access_token_masked",
            "webhook_verify_token_masked",
            "created_at",
            "updated_at",
        ]

    def get_meta_app_secret_masked(self, obj):
        return mask_secret(obj.meta_app_secret)

    def get_access_token_masked(self, obj):
        return mask_secret(obj.access_token)

    def get_webhook_verify_token_masked(self, obj):
        return mask_secret(obj.webhook_verify_token)

    def validate(self, attrs):
        instance = self.instance

        required_fields = [
            "phone_number_id",
            "whatsapp_business_account_id",
            "access_token",
            "webhook_verify_token",
        ]

        for field in required_fields:
            value = attrs.get(field, getattr(instance, field, None))
            if not value:
                raise serializers.ValidationError({field: "This field is required."})

        return attrs

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            if field in SENSITIVE_FIELDS and value == "":
                continue
            setattr(instance, field, value)

        instance.save()
        return instance
