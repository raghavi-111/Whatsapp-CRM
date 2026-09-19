from rest_framework import serializers

from .models import ContactNote, ConversationNote, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Tag name is required.")
        return value.strip()

    def validate(self, attrs):
        organization = self.context["organization"]
        name = attrs.get("name", getattr(self.instance, "name", "")).strip()
        duplicate_tags = Tag.objects.filter(organization=organization, name__iexact=name)
        if self.instance is not None:
            duplicate_tags = duplicate_tags.exclude(id=self.instance.id)
        if duplicate_tags.exists():
            raise serializers.ValidationError({"name": "A tag with this name already exists."})
        return attrs


class ContactNoteSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = ContactNote
        fields = ["id", "note", "created_by", "created_by_email", "created_at"]
        read_only_fields = ["id", "created_by", "created_by_email", "created_at"]

    def validate_note(self, value):
        if not value.strip():
            raise serializers.ValidationError("Note is required.")
        return value.strip()


class ConversationNoteSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = ConversationNote
        fields = ["id", "note", "created_by", "created_by_email", "created_at"]
        read_only_fields = ["id", "created_by", "created_by_email", "created_at"]

    def validate_note(self, value):
        if not value.strip():
            raise serializers.ValidationError("Note is required.")
        return value.strip()
