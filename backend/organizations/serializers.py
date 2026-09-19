from rest_framework import serializers
import os

from .models import Organization, OrganizationInvitation, OrganizationMember, build_unique_slug


class OrganizationSerializer(serializers.ModelSerializer):
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "owner", "current_user_role", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "owner", "current_user_role", "created_at", "updated_at"]

    def get_current_user_role(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return ""
        membership = obj.memberships.filter(user=request.user, status=OrganizationMember.STATUS_ACTIVE).first()
        return membership.role if membership else ""

    def create(self, validated_data):
        user = self.context["request"].user
        name = validated_data["name"]
        organization = Organization.objects.create(
            name=name,
            slug=build_unique_slug(name),
            owner=user,
        )
        OrganizationMember.objects.create(
            organization=organization,
            user=user,
            role=OrganizationMember.ROLE_OWNER,
            status=OrganizationMember.STATUS_ACTIVE,
        )
        return organization


class OrganizationMemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    user = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = OrganizationMember
        fields = ["id", "user", "email", "role", "status", "joined_at"]
        read_only_fields = ["id", "user", "email", "role", "status", "joined_at"]


class OrganizationMemberUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationMember
        fields = ["role", "status"]

    def validate_role(self, value):
        if value not in [OrganizationMember.ROLE_OWNER, OrganizationMember.ROLE_ADMIN, OrganizationMember.ROLE_AGENT]:
            raise serializers.ValidationError("Invalid member role.")
        return value

    def validate_status(self, value):
        if value not in [OrganizationMember.STATUS_ACTIVE, OrganizationMember.STATUS_DISABLED]:
            raise serializers.ValidationError("Invalid member status.")
        return value


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    invited_by_email = serializers.EmailField(source="invited_by.email", read_only=True)
    accepted_by_email = serializers.EmailField(source="accepted_by.email", read_only=True)
    accept_url = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationInvitation
        fields = [
            "id",
            "organization",
            "email",
            "role",
            "token",
            "status",
            "invited_by",
            "invited_by_email",
            "accepted_by",
            "accepted_by_email",
            "expires_at",
            "created_at",
            "accepted_at",
            "accept_url",
        ]
        read_only_fields = [
            "id",
            "organization",
            "token",
            "status",
            "invited_by",
            "invited_by_email",
            "accepted_by",
            "accepted_by_email",
            "expires_at",
            "created_at",
            "accepted_at",
            "accept_url",
        ]

    def get_accept_url(self, obj):
        frontend_base_url = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
        return f"{frontend_base_url}/invite/accept/{obj.token}"

    def validate_email(self, value):
        return value.strip().lower()


class OrganizationInvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=[OrganizationMember.ROLE_ADMIN, OrganizationMember.ROLE_AGENT])

    def validate_email(self, value):
        return value.strip().lower()


class OrganizationInvitationPublicSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationInvitation
        fields = ["email", "role", "status", "expires_at", "organization_name", "is_expired"]

    def get_is_expired(self, obj):
        return obj.is_expired()
