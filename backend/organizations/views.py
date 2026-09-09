from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Organization, OrganizationInvitation, OrganizationMember
from .permissions import (
    active_owner_count,
    can_invite_role,
    can_manage_member,
    can_manage_settings,
    can_manage_team,
    get_current_membership,
    is_owner,
)
from .serializers import (
    OrganizationInvitationCreateSerializer,
    OrganizationInvitationPublicSerializer,
    OrganizationInvitationSerializer,
    OrganizationMemberSerializer,
    OrganizationMemberUpdateSerializer,
    OrganizationSerializer,
)


User = get_user_model()


def no_active_organization_response():
    return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)


def permission_denied_response():
    return Response({"detail": "You do not have permission to manage this team."}, status=status.HTTP_403_FORBIDDEN)


class OrganizationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organizations = Organization.objects.filter(
            memberships__user=request.user,
            memberships__status=OrganizationMember.STATUS_ACTIVE,
        ).distinct()
        serializer = OrganizationSerializer(organizations, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        serializer = OrganizationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        organization = serializer.save()
        return Response(OrganizationSerializer(organization, context={"request": request}).data, status=status.HTTP_201_CREATED)


class CurrentOrganizationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = get_current_membership(request.user)
        if membership is None:
            return no_active_organization_response()

        return Response(OrganizationSerializer(membership.organization, context={"request": request}).data)

    def patch(self, request):
        membership = get_current_membership(request.user)
        if membership is None:
            return no_active_organization_response()
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can update organization settings."}, status=status.HTTP_403_FORBIDDEN)

        serializer = OrganizationSerializer(
            membership.organization,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class OrganizationMembersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = get_current_membership(request.user)
        if membership is None:
            return no_active_organization_response()
        if not can_manage_team(membership):
            return permission_denied_response()

        members = OrganizationMember.objects.select_related("user").filter(
            organization=membership.organization
        )
        serializer = OrganizationMemberSerializer(members, many=True)
        return Response(serializer.data)


class OrganizationMemberDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_member(self, request, member_id):
        actor = get_current_membership(request.user)
        if actor is None:
            return None, None, no_active_organization_response()
        try:
            target = OrganizationMember.objects.select_related("user", "organization").get(
                id=member_id,
                organization=actor.organization,
            )
        except OrganizationMember.DoesNotExist:
            return actor, None, Response({"detail": "Member not found."}, status=status.HTTP_404_NOT_FOUND)
        return actor, target, None

    def patch(self, request, member_id):
        actor, target, error_response = self.get_member(request, member_id)
        if error_response:
            return error_response
        if not can_manage_member(actor, target):
            return permission_denied_response()
        if target.user_id == request.user.id and target.role == OrganizationMember.ROLE_OWNER:
            return Response({"detail": "Owners cannot lower their own role."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrganizationMemberUpdateSerializer(target, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        next_role = serializer.validated_data.get("role", target.role)
        next_status = serializer.validated_data.get("status", target.status)

        if target.role == OrganizationMember.ROLE_OWNER and (
            next_role != OrganizationMember.ROLE_OWNER or next_status != OrganizationMember.STATUS_ACTIVE
        ):
            if active_owner_count(actor.organization) <= 1:
                return Response(
                    {"detail": "This organization must keep at least one active owner."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if not is_owner(actor) and next_role != OrganizationMember.ROLE_AGENT:
            return Response({"detail": "Admins can manage agents only."}, status=status.HTTP_403_FORBIDDEN)

        serializer.save()
        return Response(OrganizationMemberSerializer(target).data)

    def delete(self, request, member_id):
        actor, target, error_response = self.get_member(request, member_id)
        if error_response:
            return error_response
        if not can_manage_member(actor, target):
            return permission_denied_response()
        if target.user_id == request.user.id:
            return Response({"detail": "You cannot remove yourself from the organization."}, status=status.HTTP_400_BAD_REQUEST)
        if target.role == OrganizationMember.ROLE_OWNER and active_owner_count(actor.organization) <= 1:
            return Response(
                {"detail": "This organization must keep at least one active owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target.status = OrganizationMember.STATUS_DISABLED
        target.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationInvitationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = get_current_membership(request.user)
        if membership is None:
            return no_active_organization_response()
        if not can_manage_team(membership):
            return permission_denied_response()

        invitations = OrganizationInvitation.objects.select_related("invited_by", "accepted_by").filter(
            organization=membership.organization
        )
        return Response(OrganizationInvitationSerializer(invitations, many=True, context={"request": request}).data)

    def post(self, request):
        membership = get_current_membership(request.user)
        if membership is None:
            return no_active_organization_response()
        if not can_manage_team(membership):
            return permission_denied_response()

        serializer = OrganizationInvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        role = serializer.validated_data["role"]

        if not can_invite_role(membership, role):
            return Response({"detail": "You cannot invite a member with that role."}, status=status.HTTP_403_FORBIDDEN)
        if OrganizationMember.objects.filter(
            organization=membership.organization,
            user__email__iexact=email,
            status=OrganizationMember.STATUS_ACTIVE,
        ).exists():
            return Response({"detail": "This user is already an active member."}, status=status.HTTP_400_BAD_REQUEST)
        if OrganizationInvitation.objects.filter(
            organization=membership.organization,
            email__iexact=email,
            status=OrganizationInvitation.STATUS_PENDING,
        ).exists():
            return Response({"detail": "A pending invitation already exists for this email."}, status=status.HTTP_400_BAD_REQUEST)

        invitation = OrganizationInvitation.objects.create(
            organization=membership.organization,
            email=email,
            role=role,
            invited_by=request.user,
            expires_at=timezone.now() + timedelta(days=7),
        )
        return Response(
            OrganizationInvitationSerializer(invitation, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationInvitationCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, invitation_id):
        membership = get_current_membership(request.user)
        if membership is None:
            return no_active_organization_response()
        if not can_manage_team(membership):
            return permission_denied_response()

        try:
            invitation = OrganizationInvitation.objects.get(id=invitation_id, organization=membership.organization)
        except OrganizationInvitation.DoesNotExist:
            return Response({"detail": "Invitation not found."}, status=status.HTTP_404_NOT_FOUND)

        if invitation.status != OrganizationInvitation.STATUS_PENDING:
            return Response({"detail": "Only pending invitations can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        invitation.status = OrganizationInvitation.STATUS_CANCELLED
        invitation.save(update_fields=["status"])
        return Response(OrganizationInvitationSerializer(invitation, context={"request": request}).data)


class OrganizationInvitationPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            invitation = OrganizationInvitation.objects.select_related("organization").get(token=token)
        except OrganizationInvitation.DoesNotExist:
            return Response({"detail": "Invitation not found."}, status=status.HTTP_404_NOT_FOUND)

        if invitation.status == OrganizationInvitation.STATUS_PENDING and invitation.is_expired():
            invitation.status = OrganizationInvitation.STATUS_EXPIRED
            invitation.save(update_fields=["status"])

        return Response(OrganizationInvitationPublicSerializer(invitation).data)


class OrganizationInvitationAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, token):
        try:
            invitation = OrganizationInvitation.objects.select_for_update().select_related("organization").get(token=token)
        except OrganizationInvitation.DoesNotExist:
            return Response({"detail": "Invitation not found."}, status=status.HTTP_404_NOT_FOUND)

        if invitation.status == OrganizationInvitation.STATUS_CANCELLED:
            return Response({"detail": "This invitation has been cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        if invitation.status == OrganizationInvitation.STATUS_ACCEPTED:
            return Response({"detail": "This invitation has already been accepted."}, status=status.HTTP_400_BAD_REQUEST)
        if invitation.status == OrganizationInvitation.STATUS_EXPIRED or invitation.is_expired():
            invitation.status = OrganizationInvitation.STATUS_EXPIRED
            invitation.save(update_fields=["status"])
            return Response({"detail": "This invitation has expired."}, status=status.HTTP_400_BAD_REQUEST)

        invited_user = User.objects.filter(email__iexact=invitation.email).first()
        if invited_user is None:
            return Response(
                {"detail": "No user exists for this invitation email yet. Register first, then accept the invitation."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.user.email.lower() != invitation.email.lower():
            return Response({"detail": "This invitation belongs to a different email address."}, status=status.HTTP_403_FORBIDDEN)

        membership, _ = OrganizationMember.objects.get_or_create(
            organization=invitation.organization,
            user=request.user,
            defaults={"role": invitation.role, "status": OrganizationMember.STATUS_ACTIVE},
        )
        membership.role = invitation.role
        membership.status = OrganizationMember.STATUS_ACTIVE
        membership.save(update_fields=["role", "status"])

        invitation.status = OrganizationInvitation.STATUS_ACCEPTED
        invitation.accepted_by = request.user
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["status", "accepted_by", "accepted_at"])
        return Response(
            {
                "message": "Invitation accepted.",
                "membership": OrganizationMemberSerializer(membership).data,
            }
        )
