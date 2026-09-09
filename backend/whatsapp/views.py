from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from django.http import HttpResponse

from organizations.models import OrganizationMember
from organizations.permissions import can_manage_settings, get_current_membership

from .models import WhatsAppBusinessConfig
from .connection import WhatsAppConnectionTestError, test_whatsapp_connection
from .serializers import WhatsAppBusinessConfigSerializer
from .webhook import (
    extract_status_events,
    extract_text_messages,
    handle_status_event,
    handle_text_message_event,
    valid_webhook_signature,
    webhook_phone_number_ids,
)
from .simulation import simulate_inbound_message
from conversations.models import Conversation
from conversations.serializers import MessageSerializer


def get_current_organization(user):
    membership = (
        OrganizationMember.objects.select_related("organization")
        .filter(user=user, status=OrganizationMember.STATUS_ACTIVE)
        .order_by("-joined_at")
        .first()
    )
    return membership.organization if membership else None


class WhatsAppConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = get_current_membership(request.user)
        organization = membership.organization if membership else None
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage WhatsApp settings."}, status=status.HTTP_403_FORBIDDEN)

        try:
            config = organization.whatsapp_config
        except WhatsAppBusinessConfig.DoesNotExist:
            return Response({"detail": "WhatsApp config not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(WhatsAppBusinessConfigSerializer(config).data)


    def post(self, request):
        membership = get_current_membership(request.user)
        organization = membership.organization if membership else None
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage WhatsApp settings."}, status=status.HTTP_403_FORBIDDEN)

        if WhatsAppBusinessConfig.objects.filter(organization=organization, is_active=True).exists():
            return Response(
                {"detail": "An active WhatsApp config already exists for this organization."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = WhatsAppBusinessConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.save(organization=organization)
        return Response(WhatsAppBusinessConfigSerializer(config).data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        membership = get_current_membership(request.user)
        organization = membership.organization if membership else None
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage WhatsApp settings."}, status=status.HTTP_403_FORBIDDEN)

        try:
            config = organization.whatsapp_config
        except WhatsAppBusinessConfig.DoesNotExist:
            return Response({"detail": "WhatsApp config not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = WhatsAppBusinessConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        return Response(WhatsAppBusinessConfigSerializer(config).data)


class WhatsAppConfigTestConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        membership = get_current_membership(request.user)
        organization = membership.organization if membership else None
        if organization is None:
            return Response({"success": False, "message": "No active organization found."}, status=404)
        if not can_manage_settings(membership):
            return Response(
                {"success": False, "message": "Only owners and admins can test WhatsApp settings."},
                status=403,
            )
        try:
            config = organization.whatsapp_config
        except WhatsAppBusinessConfig.DoesNotExist:
            return Response({"success": False, "message": "WhatsApp configuration has not been saved."}, status=400)
        if not config.is_active:
            return Response({"success": False, "message": "WhatsApp configuration is inactive."}, status=400)
        if not str(config.phone_number_id or "").strip():
            return Response({"success": False, "message": "Phone Number ID is missing from the saved configuration."}, status=400)
        if not str(config.access_token or "").strip():
            return Response({"success": False, "message": "Permanent Access Token is missing from the saved configuration."}, status=400)

        try:
            data = test_whatsapp_connection(config)
        except WhatsAppConnectionTestError as error:
            return Response({"success": False, "message": error.message}, status=error.status_code)
        return Response({"success": True, "message": "WhatsApp API connection successful.", "data": data})


class WhatsAppWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        mode = request.query_params.get("hub.mode")
        verify_token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        token_matches = WhatsAppBusinessConfig.objects.filter(
            webhook_verify_token=verify_token,
            is_active=True,
        ).exists()

        if mode == "subscribe" and verify_token and challenge and token_matches:
            return HttpResponse(challenge, content_type="text/plain", status=200)

        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    def post(self, request):
        raw_body = request._request.body
        payload = request.data
        phone_number_ids = webhook_phone_number_ids(payload)
        signature = request.headers.get("X-Hub-Signature-256", "")
        configs = WhatsAppBusinessConfig.objects.filter(
            phone_number_id__in=phone_number_ids,
            is_active=True,
        ).only("meta_app_secret")
        if not any(valid_webhook_signature(raw_body, signature, config.meta_app_secret) for config in configs):
            return Response({"detail": "Invalid webhook signature."}, status=status.HTTP_403_FORBIDDEN)

        text_events = extract_text_messages(payload)
        status_events = extract_status_events(payload)

        for event in text_events:
            handle_text_message_event(event)

        for event in status_events:
            handle_status_event(event)

        return Response({"status": "received"})


class SimulateInboundSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField(required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=50)
    text = serializers.CharField(max_length=4096)
    message_id = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        if not attrs.get("conversation_id") and not str(attrs.get("phone_number", "")).strip():
            raise serializers.ValidationError("conversation_id or phone_number is required.")
        return attrs


class WhatsAppSimulateInboundView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can simulate inbound messages."}, status=403)
        serializer = SimulateInboundSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        conversation = None
        if serializer.validated_data.get("conversation_id"):
            conversation = Conversation.objects.filter(id=serializer.validated_data["conversation_id"], organization=membership.organization).first()
            if not conversation: return Response({"detail": "Conversation not found."}, status=404)
        message, duplicate = simulate_inbound_message(membership.organization, text=serializer.validated_data["text"], conversation=conversation, phone_number=serializer.validated_data.get("phone_number", ""), message_id=serializer.validated_data.get("message_id", ""))
        return Response({"detail": "Duplicate simulated message ignored." if duplicate else "Inbound message simulated.", "duplicate": duplicate, "message": MessageSerializer(message, context={"request": request}).data}, status=200 if duplicate else 201)
