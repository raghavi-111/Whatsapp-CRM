from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import OrganizationMember

from .models import Deal
from .serializers import DealSerializer


def get_current_organization(user):
    membership = (
        OrganizationMember.objects.select_related("organization")
        .filter(user=user, status=OrganizationMember.STATUS_ACTIVE)
        .order_by("-joined_at")
        .first()
    )
    return membership.organization if membership else None


class DealListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        deals = Deal.objects.select_related("contact").filter(organization=organization)
        stage = request.query_params.get("stage", "").strip()
        deal_status = request.query_params.get("status", "").strip()
        if stage:
            deals = deals.filter(stage=stage)
        if deal_status:
            deals = deals.filter(status=deal_status)

        return Response(DealSerializer(deals, many=True).data)

    def post(self, request):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = DealSerializer(
            data=request.data,
            context={"organization": organization, "request_user": request.user},
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            deal = serializer.save(organization=organization)
        from automations.models import AutomationRule
        from automations.services import enqueue_automations

        enqueue_automations(
            AutomationRule.TRIGGER_DEAL_CREATED,
            organization,
            {"contact": deal.contact, "deal": deal, "deal_stage": deal.stage},
        )
        return Response(DealSerializer(deal).data, status=status.HTTP_201_CREATED)


class DealDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_deal(self, request, deal_id):
        organization = get_current_organization(request.user)
        if organization is None:
            return None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            return Deal.objects.select_related("contact").get(id=deal_id, organization=organization), None
        except Deal.DoesNotExist:
            return None, Response({"detail": "Deal not found."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, deal_id):
        deal, error_response = self.get_deal(request, deal_id)
        if error_response:
            return error_response

        previous_stage = deal.stage
        serializer = DealSerializer(
            deal,
            data=request.data,
            partial=True,
            context={"organization": deal.organization},
        )
        serializer.is_valid(raise_exception=True)
        deal = serializer.save()
        if previous_stage != deal.stage:
            from automations.models import AutomationRule
            from automations.services import enqueue_automations

            enqueue_automations(
                AutomationRule.TRIGGER_DEAL_STAGE_CHANGED,
                deal.organization,
                {
                    "contact": deal.contact,
                    "deal": deal,
                    "previous_stage": previous_stage,
                    "deal_stage": deal.stage,
                },
            )
        return Response(serializer.data)
