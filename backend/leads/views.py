from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import OrganizationMember
from organizations.permissions import can_manage_settings, get_current_membership
from contacts.models import Contact
from pipelines.models import Deal
from pipelines.serializers import DealSerializer

from .models import Lead, Service
from .serializers import LeadSerializer, ServiceSerializer
from whatsapp.sending import normalize_phone_number


def membership_or_response(request):
    membership = get_current_membership(request.user)
    if membership is None:
        return None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
    return membership, None


class LeadPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ServiceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership, error = membership_or_response(request)
        if error: return error
        services = Service.objects.filter(organization=membership.organization)
        if request.query_params.get("active", "").lower() in ("true", "1"):
            services = services.filter(is_active=True)
        return Response(ServiceSerializer(services, many=True).data)

    def post(self, request):
        membership, error = membership_or_response(request)
        if error: return error
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage services."}, status=403)
        serializer = ServiceSerializer(data=request.data, context={"organization": membership.organization})
        serializer.is_valid(raise_exception=True)
        service = serializer.save(organization=membership.organization)
        return Response(ServiceSerializer(service).data, status=201)


class ServiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, service_id):
        membership, error = membership_or_response(request)
        if error: return None, None, error
        service = Service.objects.filter(organization=membership.organization, pk=service_id).first()
        if not service:
            return membership, None, Response({"detail": "Service not found."}, status=404)
        return membership, service, None

    def get(self, request, service_id):
        _, service, error = self.get_object(request, service_id)
        return error or Response(ServiceSerializer(service).data)

    def patch(self, request, service_id):
        membership, service, error = self.get_object(request, service_id)
        if error: return error
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage services."}, status=403)
        serializer = ServiceSerializer(service, data=request.data, partial=True, context={"organization": membership.organization})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class LeadListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership, error = membership_or_response(request)
        if error: return error
        leads = Lead.objects.select_related("service", "assigned_to", "contact", "converted_deal").filter(organization=membership.organization)
        search = request.query_params.get("search", "").strip()
        if search:
            leads = leads.filter(Q(name__icontains=search) | Q(phone__icontains=search) | Q(email__icontains=search))
        for param, field in (("service", "service_id"), ("source", "source"), ("status", "status"), ("assigned_to", "assigned_to_id")):
            value = request.query_params.get(param, "").strip()
            if value:
                leads = leads.filter(**{field: value})
        follow_up = parse_date(request.query_params.get("follow_up_date", ""))
        if follow_up:
            leads = leads.filter(next_follow_up__date=follow_up)
        ordering = request.query_params.get("ordering", "-created_at")
        if ordering in ("created_at", "-created_at", "next_follow_up", "-next_follow_up"):
            leads = leads.order_by(ordering)
        paginator = LeadPagination()
        page = paginator.paginate_queryset(leads, request)
        return paginator.get_paginated_response(LeadSerializer(page, many=True).data)

    def post(self, request):
        membership, error = membership_or_response(request)
        if error: return error
        serializer = LeadSerializer(data=request.data, context={"organization": membership.organization})
        serializer.is_valid(raise_exception=True)
        lead = serializer.save(organization=membership.organization, created_by=request.user)
        return Response(LeadSerializer(lead).data, status=201)


class LeadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, lead_id):
        membership, error = membership_or_response(request)
        if error: return None, None, error
        lead = Lead.objects.select_related("service", "assigned_to", "contact", "converted_deal").filter(organization=membership.organization, pk=lead_id).first()
        if not lead:
            return membership, None, Response({"detail": "Lead not found."}, status=404)
        return membership, lead, None

    def get(self, request, lead_id):
        _, lead, error = self.get_object(request, lead_id)
        return error or Response(LeadSerializer(lead).data)

    def patch(self, request, lead_id):
        membership, lead, error = self.get_object(request, lead_id)
        if error: return error
        serializer = LeadSerializer(lead, data=request.data, partial=True, context={"organization": membership.organization})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, lead_id):
        membership, lead, error = self.get_object(request, lead_id)
        if error: return error
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can delete leads."}, status=403)
        lead.delete()
        return Response(status=204)


class LeadConvertView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, lead_id):
        membership, error = membership_or_response(request)
        if error: return error
        with transaction.atomic():
            lead = Lead.objects.select_for_update().filter(organization=membership.organization, pk=lead_id).first()
            if not lead:
                return Response({"detail": "Lead not found."}, status=404)
            if lead.converted_deal_id or lead.status == Lead.STATUS_CONVERTED:
                return Response({"detail": "This lead has already been converted."}, status=400)
            if lead.status != Lead.STATUS_INTERESTED:
                return Response({"detail": "Only interested leads can be converted."}, status=400)
            stages = dict(Deal.STAGE_CHOICES)
            if Deal.STAGE_NEW not in stages:
                return Response({"detail": "No valid initial deal stage is configured."}, status=400)
            if lead.contact_id is None:
                normalized_phone = normalize_phone_number(lead.phone)
                contact = next(
                    (
                        candidate
                        for candidate in Contact.objects.select_for_update().filter(organization=membership.organization)
                        if normalize_phone_number(candidate.phone_number) == normalized_phone
                    ),
                    None,
                )
                if contact is None:
                    contact = Contact.objects.create(
                        organization=membership.organization,
                        full_name=lead.name,
                        phone_number=normalized_phone,
                        email=lead.email,
                        source=(
                            Contact.SOURCE_LEAD_COLLECTOR
                            if lead.source == Lead.SOURCE_LEAD_COLLECTOR
                            else Contact.SOURCE_MANUAL
                        ),
                        created_by=request.user,
                    )
                lead.contact = contact
            deal = Deal.objects.create(
                organization=membership.organization, contact=lead.contact, title=lead.name,
                stage=Deal.STAGE_NEW, status=Deal.STATUS_OPEN, source=Deal.SOURCE_MANUAL, notes=lead.notes,
            )
            lead.converted_deal = deal
            lead.status = Lead.STATUS_CONVERTED
            lead.save(update_fields=["contact", "converted_deal", "status", "updated_at"])
        return Response(DealSerializer(deal).data, status=201)


class LeadAssigneeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership, error = membership_or_response(request)
        if error: return error
        members = OrganizationMember.objects.select_related("user").filter(
            organization=membership.organization, status=OrganizationMember.STATUS_ACTIVE
        )
        return Response([{"id": item.user_id, "email": item.user.email, "role": item.role} for item in members])
