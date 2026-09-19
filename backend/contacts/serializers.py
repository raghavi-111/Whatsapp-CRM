from rest_framework import serializers

from .models import Contact, ContactCategory


class ContactSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = [
            "id",
            "organization",
            "full_name",
            "phone_number",
            "email",
            "company_name",
            "category",
            "source",
            "status",
            "notes",
            "tags",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_by", "created_at", "updated_at"]

    def get_tags(self, obj):
        return [
            {"id": tag.id, "name": tag.name, "color": tag.color}
            for tag in obj.tags.all()
        ]

    def get_category(self, obj):
        return {"id": obj.category_id, "name": obj.category.name} if obj.category_id else None


    def validate_phone_number(self, value):
        if not value:
            raise serializers.ValidationError("Phone number is required.")
        return value.strip()

    def validate(self, attrs):
        organization = self.context["organization"]
        phone_number = attrs.get("phone_number", getattr(self.instance, "phone_number", None))
        duplicate_contacts = Contact.objects.filter(
            organization=organization,
            phone_number=phone_number,
        )

        if self.instance is not None:
            duplicate_contacts = duplicate_contacts.exclude(id=self.instance.id)

        if duplicate_contacts.exists():
            raise serializers.ValidationError(
                {"phone_number": "A contact with this phone number already exists in this organization."}
            )

        return attrs


class ContactCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactCategory
        fields = ["id", "name"]
