import os
import zipfile

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from conversations.models import Conversation, Message
from conversations.serializers import MessageSerializer
from organizations.models import OrganizationMember
from organizations.permissions import can_manage_settings, get_current_membership

from .models import AutomationLog, AutomationMedia, AutomationRule, Media
from .serializers import AutomationLogSerializer, AutomationMediaSerializer, AutomationRuleSerializer, MediaSerializer


class SimulateInboundMessageSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField(required=True)
    text = serializers.CharField(required=True, allow_blank=False, max_length=4096)

    def validate_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Inbound message text is required.")
        return value


def get_current_organization(user):
    membership = (
        OrganizationMember.objects.select_related("organization")
        .filter(user=user, status=OrganizationMember.STATUS_ACTIVE)
        .order_by("-joined_at")
        .first()
    )
    return membership.organization if membership else None


def get_rules_for_user(user):
    organization = get_current_organization(user)
    if organization is None:
        return None, AutomationRule.objects.none()

    return organization, AutomationRule.objects.filter(organization=organization)


class AutomationRuleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage automations."}, status=status.HTTP_403_FORBIDDEN)
        organization, rules = get_rules_for_user(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(AutomationRuleSerializer(rules, many=True).data)

    def post(self, request):
        membership = get_current_membership(request.user)
        organization = membership.organization if membership else None
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage automations."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AutomationRuleSerializer(data=request.data, context={"organization": organization})
        serializer.is_valid(raise_exception=True)
        rule = serializer.save(organization=organization, created_by=request.user)
        return Response(AutomationRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


class AutomationRuleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_rule(self, request, rule_id):
        organization, rules = get_rules_for_user(request.user)
        if organization is None:
            return None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            return rules.get(id=rule_id), None
        except AutomationRule.DoesNotExist:
            return None, Response({"detail": "Automation rule not found."}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, rule_id):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage automations."}, status=status.HTTP_403_FORBIDDEN)
        rule, error_response = self.get_rule(request, rule_id)
        if error_response:
            return error_response
        return Response(AutomationRuleSerializer(rule).data)

    def patch(self, request, rule_id):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage automations."}, status=status.HTTP_403_FORBIDDEN)
        rule, error_response = self.get_rule(request, rule_id)
        if error_response:
            return error_response

        serializer = AutomationRuleSerializer(rule, data=request.data, partial=True, context={"organization": rule.organization})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, rule_id):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage automations."}, status=status.HTTP_403_FORBIDDEN)
        rule, error_response = self.get_rule(request, rule_id)
        if error_response:
            return error_response

        rule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AutomationLogListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage automations."}, status=status.HTTP_403_FORBIDDEN)
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        logs = AutomationLog.objects.select_related("rule").filter(organization=organization)
        rule_id = request.query_params.get("rule")
        if rule_id:
            logs = logs.filter(rule_id=rule_id)
        logs = logs[:100]
        return Response(AutomationLogSerializer(logs, many=True).data)


MEDIA_MIME_TYPES = {
    "image": {"image/jpeg", "image/png", "image/webp"},
    "document": {"application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "video": {"video/mp4"},
    "audio": {"audio/mpeg", "audio/ogg", "audio/mp4", "audio/x-m4a"},
}
MEDIA_SIZE_LIMITS = {"image": 5 * 1024 * 1024, "document": 100 * 1024 * 1024, "video": 16 * 1024 * 1024, "audio": 16 * 1024 * 1024}

# Kept explicit so extension, declared MIME, and file signature must all agree.
FLOW_MEDIA_EXTENSIONS = {
    ".jpg": ("image", {"image/jpeg"}), ".jpeg": ("image", {"image/jpeg"}), ".png": ("image", {"image/png"}),
    ".webp": ("image", {"image/webp"}), ".pdf": ("document", {"application/pdf"}),
    ".doc": ("document", {"application/msword", "application/octet-stream"}),
    ".docx": ("document", {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"}),
    ".mp4": ("video", {"video/mp4"}), ".mp3": ("audio", {"audio/mpeg", "audio/mp3"}),
    ".wav": ("audio", {"audio/wav", "audio/x-wav", "audio/wave"}),
}


def _has_valid_signature(upload, extension):
    header = upload.read(16)
    upload.seek(0)
    if extension in {".jpg", ".jpeg"}: return header.startswith(b"\xff\xd8\xff")
    if extension == ".png": return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp": return header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    if extension == ".pdf": return header.startswith(b"%PDF-")
    if extension == ".doc": return header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if extension == ".mp4": return len(header) >= 12 and header[4:8] == b"ftyp"
    if extension == ".mp3": return header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xff and header[1] & 0xe0 == 0xe0)
    if extension == ".wav": return header[:4] == b"RIFF" and header[8:12] == b"WAVE"
    if extension == ".docx":
        try:
            with zipfile.ZipFile(upload) as archive:
                return "[Content_Types].xml" in archive.namelist() and any(name.startswith("word/") for name in archive.namelist())
        except (zipfile.BadZipFile, OSError):
            return False
        finally:
            upload.seek(0)
    return False


class MediaListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        membership = get_current_membership(request.user)
        if membership is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        items = Media.objects.filter(organization=membership.organization)
        return Response(MediaSerializer(items, many=True, context={"request": request}).data)


class MediaUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        membership = get_current_membership(request.user)
        if membership is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "A file is required."}, status=status.HTTP_400_BAD_REQUEST)
        filename = os.path.basename(upload.name)
        extension = os.path.splitext(filename)[1].lower()
        specification = FLOW_MEDIA_EXTENSIONS.get(extension)
        if specification is None:
            return Response({"detail": "Unsupported file extension."}, status=status.HTTP_400_BAD_REQUEST)
        media_type, mime_types = specification
        mime_type = (getattr(upload, "content_type", "") or "").lower()
        if mime_type not in mime_types or not _has_valid_signature(upload, extension):
            return Response({"detail": "The file content or MIME type is invalid."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size <= 0 or upload.size > MEDIA_SIZE_LIMITS[media_type]:
            limit_mb = MEDIA_SIZE_LIMITS[media_type] // (1024 * 1024)
            return Response({"detail": f"{media_type.title()} files must be non-empty and {limit_mb}MB or smaller."}, status=status.HTTP_400_BAD_REQUEST)
        item = Media.objects.create(organization=membership.organization, file=upload, filename=filename, mime_type=mime_type, media_type=media_type, size=upload.size, created_by=request.user)
        return Response(MediaSerializer(item, context={"request": request}).data, status=status.HTTP_201_CREATED)


class AutomationMediaListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage automation media."}, status=status.HTTP_403_FORBIDDEN)
        media = AutomationMedia.objects.filter(organization=membership.organization)
        return Response(AutomationMediaSerializer(media, many=True, context={"request": request}).data)

    def post(self, request):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage automation media."}, status=status.HTTP_403_FORBIDDEN)
        upload = request.FILES.get("file")
        media_type = str(request.data.get("media_type", "")).strip()
        if not upload or media_type not in MEDIA_MIME_TYPES:
            return Response({"detail": "A file and valid media_type are required."}, status=status.HTTP_400_BAD_REQUEST)
        mime_type = getattr(upload, "content_type", "") or ""
        if mime_type not in MEDIA_MIME_TYPES[media_type]:
            return Response({"detail": f"Unsupported file type for {media_type}."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MEDIA_SIZE_LIMITS[media_type]:
            limit_mb = MEDIA_SIZE_LIMITS[media_type] // (1024 * 1024)
            return Response({"detail": f"{media_type.title()} files must be {limit_mb}MB or smaller."}, status=status.HTTP_400_BAD_REQUEST)
        item = AutomationMedia.objects.create(organization=membership.organization, file=upload, filename=os.path.basename(upload.name), mime_type=mime_type, media_type=media_type, size=upload.size, created_by=request.user)
        return Response(AutomationMediaSerializer(item, context={"request": request}).data, status=status.HTTP_201_CREATED)


class AutomationSimulateInboundMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        membership = get_current_membership(request.user)
        organization = membership.organization if membership else None
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can simulate inbound messages."}, status=status.HTTP_403_FORBIDDEN)

        serializer = SimulateInboundMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            conversation = Conversation.objects.select_related("contact").get(
                id=serializer.validated_data["conversation_id"],
                organization=organization,
            )
        except Conversation.DoesNotExist:
            return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        from whatsapp.simulation import simulate_inbound_message
        message, duplicate = simulate_inbound_message(organization, text=serializer.validated_data["text"], conversation=conversation, message_id=str(request.data.get("message_id", "")))

        return Response(
            {
                "detail": "Duplicate simulated message ignored." if duplicate else "Inbound message simulated.",
                "duplicate": duplicate,
                "message": MessageSerializer(message, context={"request": request}).data,
            },
            status=status.HTTP_200_OK if duplicate else status.HTTP_201_CREATED,
        )
