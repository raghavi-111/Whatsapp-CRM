from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from conversations.models import Conversation
from conversations.serializers import ConversationSerializer
from organizations.models import OrganizationMember
from organizations.permissions import can_manage_settings, get_current_membership
from automations.models import AutomationRule
from automations.services import enqueue_automations

from .models import Contact, ContactCategory
from .serializers import ContactCategorySerializer, ContactSerializer
from lead_collector.services.whatsapp_contact_import import ensure_contact_categories
from .services.excel_whatsapp_import import WorkbookError, commit, inspect_sheet, preview, store_workbook


def get_current_organization(user):
    membership = (
        OrganizationMember.objects.select_related("organization")
        .filter(user=user, status=OrganizationMember.STATUS_ACTIVE)
        .order_by("-joined_at")
        .first()
    )
    return membership.organization if membership else None


def get_contacts_for_user(user):
    organization = get_current_organization(user)
    if organization is None:
        return None, Contact.objects.none()

    return organization, Contact.objects.filter(organization=organization)


class ContactListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, contacts = get_contacts_for_user(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        search = request.query_params.get("search", "").strip()
        contact_status = request.query_params.get("status", "").strip()
        source = request.query_params.get("source", "").strip()
        category = request.query_params.get("category", "").strip()

        if search:
            contacts = contacts.filter(
                Q(full_name__icontains=search)
                | Q(phone_number__icontains=search)
                | Q(email__icontains=search)
                | Q(company_name__icontains=search)
            )

        if contact_status:
            contacts = contacts.filter(status=contact_status)

        if source:
            contacts = contacts.filter(source=source)
        if category:
            contacts = contacts.filter(category_id=category)

        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)

    def post(self, request):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ContactSerializer(data=request.data, context={"organization": organization})
        serializer.is_valid(raise_exception=True)
        contact = serializer.save(organization=organization, created_by=request.user)
        enqueue_automations(AutomationRule.TRIGGER_CONTACT_CREATED, organization, {"contact": contact})
        return Response(ContactSerializer(contact).data, status=status.HTTP_201_CREATED)


class ContactCategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        ensure_contact_categories(organization)
        categories = ContactCategory.objects.filter(organization=organization).order_by("name")
        return Response(ContactCategorySerializer(categories, many=True).data)


class ExcelWhatsAppWorkbookView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        organization = get_current_organization(request.user)
        if not organization: return Response({"detail": "No active organization found."}, status=404)
        uploaded = request.FILES.get("file")
        if not uploaded: return Response({"detail": "Choose an .xlsx workbook."}, status=400)
        try: return Response(store_workbook(request.user, organization, uploaded))
        except WorkbookError as exc: return Response({"detail": str(exc)}, status=400)


class ExcelWhatsAppSheetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization = get_current_organization(request.user)
        if not organization: return Response({"detail": "No active organization found."}, status=404)
        try: return Response(inspect_sheet(request.data.get("token", ""), request.user, organization, request.data.get("sheet", "")))
        except WorkbookError as exc: return Response({"detail": str(exc)}, status=400)


def _excel_options(data):
    return (data.get("token", ""), data.get("sheet", ""), data.get("mappings") or {}, data.get("default_category_id"), data.get("confirmed") is True)


class ExcelWhatsAppPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization = get_current_organization(request.user)
        if not organization: return Response({"detail": "No active organization found."}, status=404)
        try: return Response(preview(request.data.get("token", ""), request.user, organization, request.data.get("sheet", ""), request.data.get("mappings") or {}, request.data.get("default_category_id"), request.data.get("confirmed") is True))
        except WorkbookError as exc: return Response({"detail": str(exc)}, status=400)


class ExcelWhatsAppCommitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization = get_current_organization(request.user)
        if not organization: return Response({"detail": "No active organization found."}, status=404)
        try: return Response(commit(request.data.get("token", ""), request.user, organization, request.data.get("sheet", ""), request.data.get("mappings") or {}, request.data.get("default_category_id"), request.data.get("confirmed") is True))
        except WorkbookError as exc: return Response({"detail": str(exc)}, status=400)


class ContactDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_contact(self, request, contact_id):
        organization, contacts = get_contacts_for_user(request.user)
        if organization is None:
            return None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            return contacts.get(id=contact_id), None
        except Contact.DoesNotExist:
            return None, Response({"detail": "Contact not found."}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, contact_id):
        contact, error_response = self.get_contact(request, contact_id)
        if error_response:
            return error_response

        return Response(ContactSerializer(contact).data)

    def patch(self, request, contact_id):
        contact, error_response = self.get_contact(request, contact_id)
        if error_response:
            return error_response

        serializer = ContactSerializer(
            contact,
            data=request.data,
            partial=True,
            context={"organization": contact.organization},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, contact_id):
        contact, error_response = self.get_contact(request, contact_id)
        if error_response:
            return error_response
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can delete contacts."}, status=status.HTTP_403_FORBIDDEN)

        contact.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContactStartConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contact_id):
        organization, contacts = get_contacts_for_user(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            contact = contacts.get(id=contact_id)
        except Contact.DoesNotExist:
            return Response({"detail": "Contact not found."}, status=status.HTTP_404_NOT_FOUND)

        conversation, created = Conversation.objects.get_or_create(
            organization=organization,
            contact=contact,
            channel=Conversation.CHANNEL_WHATSAPP,
            status=Conversation.STATUS_OPEN,
            defaults={"status": Conversation.STATUS_OPEN},
        )

        if created:
            enqueue_automations(
                AutomationRule.TRIGGER_CONVERSATION_CREATED,
                organization,
                {"contact": contact, "conversation": conversation},
            )

        return Response(
            {
                "conversation_id": conversation.id,
                "created": created,
                "conversation": ConversationSerializer(
                    conversation,
                    context={"organization": organization},
                ).data,
                "contact": ContactSerializer(contact).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
