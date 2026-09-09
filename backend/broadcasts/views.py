from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import OrganizationMember
from support.models import Tag

from .models import BroadcastCampaign
from .serializers import BroadcastCampaignSerializer, BroadcastEstimateSerializer, BroadcastScheduleSerializer
from .services import estimate_recipients, send_campaign_now

import logging


logger = logging.getLogger(__name__)


def get_current_organization(user):
    membership = (
        OrganizationMember.objects.select_related("organization")
        .filter(user=user, status=OrganizationMember.STATUS_ACTIVE)
        .order_by("-joined_at")
        .first()
    )
    return membership.organization if membership else None


class BroadcastCampaignListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        campaigns = (
            BroadcastCampaign.objects.select_related("template", "created_by")
            .prefetch_related("selected_tags")
            .filter(organization=organization)
        )
        return Response(BroadcastCampaignSerializer(campaigns, many=True, context={"organization": organization}).data)

    def post(self, request):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = BroadcastCampaignSerializer(data=request.data, context={"organization": organization})
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save(organization=organization, created_by=request.user)
        return Response(BroadcastCampaignSerializer(campaign, context={"organization": organization}).data, status=status.HTTP_201_CREATED)


class BroadcastCampaignDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_campaign(self, request, campaign_id):
        organization = get_current_organization(request.user)
        if organization is None:
            return None, None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        campaign = (
            BroadcastCampaign.objects.select_related("template", "created_by")
            .prefetch_related("selected_tags", "recipients")
            .filter(id=campaign_id, organization=organization)
            .first()
        )
        if campaign is None:
            return organization, None, Response({"detail": "Campaign not found."}, status=status.HTTP_404_NOT_FOUND)
        return organization, campaign, None

    def get(self, request, campaign_id):
        organization, campaign, error_response = self.get_campaign(request, campaign_id)
        if error_response:
            return error_response
        return Response(BroadcastCampaignSerializer(campaign, context={"organization": organization}).data)

    def patch(self, request, campaign_id):
        organization, campaign, error_response = self.get_campaign(request, campaign_id)
        if error_response:
            return error_response
        serializer = BroadcastCampaignSerializer(
            campaign,
            data=request.data,
            partial=True,
            context={"organization": organization},
        )
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()
        return Response(BroadcastCampaignSerializer(campaign, context={"organization": organization}).data)


class BroadcastEstimateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = BroadcastEstimateSerializer(data=request.data, context={"organization": organization})
        serializer.is_valid(raise_exception=True)
        tag_ids = serializer.validated_data.get("selected_tag_ids", [])
        tags = Tag.objects.filter(id__in=tag_ids, organization=organization)
        count = estimate_recipients(
            organization,
            serializer.validated_data["audience_type"],
            selected_tags=tags,
            contact_status=serializer.validated_data.get("contact_status", ""),
            contact_source=serializer.validated_data.get("contact_source", ""),
        )
        return Response({"recipient_count": count})


class BroadcastSendNowView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        campaign = BroadcastCampaign.objects.filter(id=campaign_id, organization=organization).first()
        if campaign is None:
            return Response({"detail": "Campaign not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            campaign = send_campaign_now(campaign)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BroadcastCampaignSerializer(campaign, context={"organization": organization}).data)


class BroadcastScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        campaign = BroadcastCampaign.objects.filter(id=campaign_id, organization=organization).first()
        if campaign is None:
            return Response({"detail": "Campaign not found."}, status=status.HTTP_404_NOT_FOUND)
        if campaign.status != BroadcastCampaign.STATUS_DRAFT:
            return Response({"detail": "Only draft campaigns can be scheduled."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = BroadcastScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        campaign.scheduled_at = serializer.validated_data["scheduled_at"]
        campaign.status = BroadcastCampaign.STATUS_SCHEDULED
        campaign.save(update_fields=["scheduled_at", "status", "updated_at"])
        try:
            from .tasks import send_scheduled_campaign

            send_scheduled_campaign.apply_async(args=[campaign.id], eta=campaign.scheduled_at)
        except Exception as error:
            logger.warning("Unable to queue scheduled broadcast id=%s error=%s", campaign.id, error)
        return Response(BroadcastCampaignSerializer(campaign, context={"organization": organization}).data)


class BroadcastCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        campaign = BroadcastCampaign.objects.filter(id=campaign_id, organization=organization).first()
        if campaign is None:
            return Response({"detail": "Campaign not found."}, status=status.HTTP_404_NOT_FOUND)
        if campaign.status not in [BroadcastCampaign.STATUS_DRAFT, BroadcastCampaign.STATUS_SCHEDULED]:
            return Response({"detail": "Only draft or scheduled campaigns can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)
        campaign.status = BroadcastCampaign.STATUS_CANCELLED
        campaign.save(update_fields=["status", "updated_at"])
        return Response(BroadcastCampaignSerializer(campaign, context={"organization": organization}).data)
