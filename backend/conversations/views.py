from django.db.models import Q
import uuid

from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from automations.models import AutomationRule
from automations.services import enqueue_automations
from organizations.models import OrganizationMember
from realtime.utils import broadcast_inbox_event
from whatsapp.models import WhatsAppBusinessConfig
from whatsapp.sending import (
    WhatsAppSendError,
    get_send_mode,
    send_whatsapp_media_message,
    send_whatsapp_text_message,
    upload_whatsapp_media,
)

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer


MEDIA_MESSAGE_TYPES = {
    Message.TYPE_IMAGE,
    Message.TYPE_DOCUMENT,
    Message.TYPE_AUDIO,
    Message.TYPE_VIDEO,
}
MAX_MEDIA_UPLOAD_SIZE = 16 * 1024 * 1024
ALLOWED_MEDIA_MIME_TYPES = {
    Message.TYPE_IMAGE: {"image/jpeg", "image/png", "image/webp"},
    Message.TYPE_DOCUMENT: {
        "application/pdf",
        "text/plain",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    Message.TYPE_AUDIO: {"audio/aac", "audio/mp4", "audio/mpeg", "audio/ogg", "audio/webm", "audio/wav"},
    Message.TYPE_VIDEO: {"video/mp4", "video/3gpp", "video/quicktime", "video/webm"},
}


class MediaMessageUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    message_type = serializers.ChoiceField(choices=sorted(MEDIA_MESSAGE_TYPES))
    caption = serializers.CharField(required=False, allow_blank=True, max_length=1024)

    def validate(self, attrs):
        upload = attrs["file"]
        message_type = attrs["message_type"]
        mime_type = getattr(upload, "content_type", "") or ""

        if upload.size > MAX_MEDIA_UPLOAD_SIZE:
            raise serializers.ValidationError({"file": "Media file must be 16MB or smaller."})

        if mime_type not in ALLOWED_MEDIA_MIME_TYPES[message_type]:
            raise serializers.ValidationError({"file": f"Unsupported MIME type for {message_type}: {mime_type}."})

        return attrs


def get_current_organization(user):
    membership = (
        OrganizationMember.objects.select_related("organization")
        .filter(user=user, status=OrganizationMember.STATUS_ACTIVE)
        .order_by("-joined_at")
        .first()
    )
    return membership.organization if membership else None


def get_conversations_for_user(user):
    organization = get_current_organization(user)
    if organization is None:
        return None, Conversation.objects.none()

    conversations = Conversation.objects.select_related("contact", "assigned_to").prefetch_related("contact__tags").filter(
        organization=organization
    )
    return organization, conversations


class ConversationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, conversations = get_conversations_for_user(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        search = request.query_params.get("search", "").strip()
        conversation_status = request.query_params.get("status", "").strip()
        assigned_to = request.query_params.get("assigned_to", "").strip()
        ordering = request.query_params.get("ordering", "-last_message_at").strip()

        if search:
            conversations = conversations.filter(
                Q(contact__full_name__icontains=search) | Q(contact__phone_number__icontains=search)
            )

        if conversation_status:
            conversations = conversations.filter(status=conversation_status)

        if assigned_to:
            if assigned_to == "unassigned":
                conversations = conversations.filter(assigned_to__isnull=True)
            else:
                conversations = conversations.filter(assigned_to_id=assigned_to)

        if ordering in ["last_message_at", "-last_message_at", "created_at", "-created_at"]:
            conversations = conversations.order_by(ordering, "-created_at")

        serializer = ConversationSerializer(conversations, many=True, context={"organization": organization})
        return Response(serializer.data)

    def post(self, request):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ConversationSerializer(data=request.data, context={"organization": organization})
        serializer.is_valid(raise_exception=True)
        conversation = serializer.save(organization=organization)
        enqueue_automations(
            AutomationRule.TRIGGER_CONVERSATION_CREATED,
            organization,
            {"contact": conversation.contact, "conversation": conversation},
        )
        return Response(
            ConversationSerializer(conversation, context={"organization": organization}).data,
            status=status.HTTP_201_CREATED,
        )


class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_conversation(self, request, conversation_id):
        organization, conversations = get_conversations_for_user(request.user)
        if organization is None:
            return None, None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            return organization, conversations.get(id=conversation_id), None
        except Conversation.DoesNotExist:
            return organization, None, Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, conversation_id):
        organization, conversation, error_response = self.get_conversation(request, conversation_id)
        if error_response:
            return error_response

        return Response(ConversationSerializer(conversation, context={"organization": organization}).data)

    def patch(self, request, conversation_id):
        organization, conversation, error_response = self.get_conversation(request, conversation_id)
        if error_response:
            return error_response

        serializer = ConversationSerializer(
            conversation,
            data=request.data,
            partial=True,
            context={"organization": organization},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ConversationMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get_conversation(self, request, conversation_id):
        organization, conversations = get_conversations_for_user(request.user)
        if organization is None:
            return None, None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            return organization, conversations.get(id=conversation_id), None
        except Conversation.DoesNotExist:
            return organization, None, Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, conversation_id):
        organization, conversation, error_response = self.get_conversation(request, conversation_id)
        if error_response:
            return error_response

        messages = Message.objects.filter(organization=organization, conversation=conversation)
        return Response(MessageSerializer(messages, many=True, context={"request": request}).data)

    def post(self, request, conversation_id):
        organization, conversation, error_response = self.get_conversation(request, conversation_id)
        if error_response:
            return error_response

        data = {
            "sender_type": Message.SENDER_AGENT,
            "direction": Message.DIRECTION_OUTBOUND,
            "message_type": Message.TYPE_TEXT,
            "delivery_status": Message.DELIVERY_PENDING,
            **request.data,
        }

        is_agent_outbound_text = (
            data.get("sender_type") == Message.SENDER_AGENT
            and data.get("direction") == Message.DIRECTION_OUTBOUND
            and data.get("message_type") == Message.TYPE_TEXT
        )

        if is_agent_outbound_text:
            try:
                config = WhatsAppBusinessConfig.objects.filter(
                    organization=organization,
                    is_active=True,
                ).first()
                send_result = send_whatsapp_text_message(
                    config=config,
                    to_phone_number=conversation.contact.phone_number,
                    text=data.get("text", ""),
                )
                data["delivery_status"] = Message.DELIVERY_SENT
                data["external_message_id"] = send_result.external_message_id
            except WhatsAppSendError as send_error:
                data["delivery_status"] = Message.DELIVERY_FAILED
                serializer = MessageSerializer(
                    data=data,
                    context={"organization": organization, "conversation": conversation},
                )
                serializer.is_valid(raise_exception=True)
                message = serializer.save(organization=organization, conversation=conversation)
                conversation.last_message_at = message.sent_at or message.created_at
                conversation.save(update_fields=["last_message_at", "updated_at"])
                broadcast_inbox_event(
                    organization.id,
                    "message.created",
                    conversation_id=conversation.id,
                    message_id=message.id,
                    contact_id=conversation.contact_id,
                    delivery_status=message.delivery_status,
                )
                return Response(
                    {
                        "detail": str(send_error),
                        "message": MessageSerializer(message, context={"request": request}).data,
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        serializer = MessageSerializer(
            data=data,
            context={"organization": organization, "conversation": conversation},
        )
        serializer.is_valid(raise_exception=True)
        message = serializer.save(organization=organization, conversation=conversation)
        conversation.last_message_at = message.sent_at or message.created_at
        conversation.save(update_fields=["last_message_at", "updated_at"])
        broadcast_inbox_event(
            organization.id,
            "message.created",
            conversation_id=conversation.id,
            message_id=message.id,
            contact_id=conversation.contact_id,
            delivery_status=message.delivery_status,
        )
        return Response(MessageSerializer(message, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ConversationMediaMessageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_conversation(self, request, conversation_id):
        organization, conversations = get_conversations_for_user(request.user)
        if organization is None:
            return None, None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            return organization, conversations.get(id=conversation_id), None
        except Conversation.DoesNotExist:
            return organization, None, Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, conversation_id):
        organization, conversation, error_response = self.get_conversation(request, conversation_id)
        if error_response:
            return error_response

        serializer = MediaMessageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        upload = serializer.validated_data["file"]
        message_type = serializer.validated_data["message_type"]
        caption = serializer.validated_data.get("caption", "")
        mime_type = getattr(upload, "content_type", "") or ""
        filename = upload.name or f"{message_type}-upload"
        config = WhatsAppBusinessConfig.objects.filter(organization=organization, is_active=True).first()

        delivery_status = Message.DELIVERY_PENDING
        external_message_id = ""
        meta_media_id = ""
        response_status = status.HTTP_201_CREATED
        response_detail = "Media message sent."

        try:
            if get_send_mode() == "mock":
                meta_media_id = f"mock-media-{uuid.uuid4()}"
                external_message_id = f"mock-wamid-{uuid.uuid4()}"
                delivery_status = Message.DELIVERY_SENT
            else:
                meta_media_id, _ = upload_whatsapp_media(config, upload, mime_type)
                send_result = send_whatsapp_media_message(
                    config=config,
                    to_phone_number=conversation.contact.phone_number,
                    message_type=message_type,
                    meta_media_id=meta_media_id,
                    caption=caption,
                    filename=filename,
                )
                external_message_id = send_result.external_message_id
                delivery_status = Message.DELIVERY_SENT
        except WhatsAppSendError as send_error:
            delivery_status = Message.DELIVERY_FAILED
            response_status = status.HTTP_502_BAD_GATEWAY
            response_detail = str(send_error)

        message = Message.objects.create(
            organization=organization,
            conversation=conversation,
            sender_type=Message.SENDER_AGENT,
            direction=Message.DIRECTION_OUTBOUND,
            message_type=message_type,
            text=caption,
            media_file=upload,
            media_mime_type=mime_type,
            media_filename=filename,
            media_size=upload.size,
            meta_media_id=meta_media_id,
            external_message_id=external_message_id,
            delivery_status=delivery_status,
        )

        conversation.last_message_at = message.sent_at or message.created_at
        conversation.save(update_fields=["last_message_at", "updated_at"])
        broadcast_inbox_event(
            organization.id,
            "message.created",
            conversation_id=conversation.id,
            message_id=message.id,
            contact_id=conversation.contact_id,
            delivery_status=message.delivery_status,
        )

        response_data = {
            "message": response_detail,
            "data": MessageSerializer(message, context={"request": request}).data,
        }
        return Response(response_data, status=response_status)
