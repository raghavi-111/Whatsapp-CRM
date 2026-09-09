import logging

from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from contacts.models import Contact
from conversations.models import Conversation, Message
from organizations.models import OrganizationMember
from organizations.permissions import can_manage_settings, get_current_membership
from realtime.utils import broadcast_inbox_event
from whatsapp.models import WhatsAppBusinessConfig
from whatsapp.sending import WhatsAppSendError, send_whatsapp_template_message

from .models import MessageTemplate
from .serializers import MessageTemplateSerializer, SendTemplateSerializer


logger = logging.getLogger(__name__)


def count_json_template_references(items, template_id):
    template_id = str(template_id)
    return sum(
        1
        for item_list in items
        if any(str(item.get("template_id", "")) == template_id for item in item_list if isinstance(item, dict))
    )


def get_template_dependencies(template):
    from automations.models import AutomationRule
    from flows.models import CustomerFlow

    dependencies = {}
    broadcast_count = template.broadcast_campaigns.count()
    if broadcast_count:
        dependencies["broadcasts"] = broadcast_count

    automation_count = count_json_template_references(
        AutomationRule.objects.filter(organization=template.organization).values_list("actions_json", flat=True),
        template.id,
    )
    if automation_count:
        dependencies["automations"] = automation_count

    flow_count = count_json_template_references(
        CustomerFlow.objects.filter(organization=template.organization).values_list("steps_json", flat=True),
        template.id,
    )
    if flow_count:
        dependencies["flows"] = flow_count
    return dependencies


def format_dependency_error(dependencies):
    descriptions = [
        f"{count} {dependency[:-1] if count == 1 else dependency}"
        for dependency, count in dependencies.items()
    ]
    return f"This template cannot be deleted because it is currently used by {', '.join(descriptions)}."


def get_current_organization(user):
    membership = (
        OrganizationMember.objects.select_related("organization")
        .filter(user=user, status=OrganizationMember.STATUS_ACTIVE)
        .order_by("-joined_at")
        .first()
    )
    return membership.organization if membership else None


def get_templates_for_user(user):
    organization = get_current_organization(user)
    if organization is None:
        return None, MessageTemplate.objects.none()

    return organization, MessageTemplate.objects.filter(organization=organization)


class MessageTemplateListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, templates = get_templates_for_user(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        search = request.query_params.get("search", "").strip()
        category = request.query_params.get("category", "").strip()
        template_status = request.query_params.get("status", "").strip()
        language = request.query_params.get("language", "").strip()

        if search:
            templates = templates.filter(Q(name__icontains=search) | Q(body_text__icontains=search))
        if category:
            templates = templates.filter(category=category)
        if template_status:
            templates = templates.filter(status=template_status)
        if language:
            templates = templates.filter(language__iexact=language)

        serializer = MessageTemplateSerializer(templates, many=True)
        return Response(serializer.data)

    def post(self, request):
        membership = get_current_membership(request.user)
        organization = membership.organization if membership else None
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage templates."}, status=status.HTTP_403_FORBIDDEN)

        serializer = MessageTemplateSerializer(data=request.data, context={"organization": organization})
        serializer.is_valid(raise_exception=True)
        template = serializer.save(organization=organization, created_by=request.user)
        return Response(MessageTemplateSerializer(template).data, status=status.HTTP_201_CREATED)


class MessageTemplateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_template(self, request, template_id):
        organization, templates = get_templates_for_user(request.user)
        if organization is None:
            return None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            return templates.get(id=template_id), None
        except MessageTemplate.DoesNotExist:
            return None, Response({"detail": "Template not found."}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, template_id):
        template, error_response = self.get_template(request, template_id)
        if error_response:
            return error_response

        return Response(MessageTemplateSerializer(template).data)

    def patch(self, request, template_id):
        template, error_response = self.get_template(request, template_id)
        if error_response:
            return error_response
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage templates."}, status=status.HTTP_403_FORBIDDEN)

        serializer = MessageTemplateSerializer(
            template,
            data=request.data,
            partial=True,
            context={"organization": template.organization},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, template_id):
        template, error_response = self.get_template(request, template_id)
        if error_response:
            return error_response
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage templates."}, status=status.HTTP_403_FORBIDDEN)

        dependencies = get_template_dependencies(template)
        if dependencies:
            return Response(
                {"detail": format_dependency_error(dependencies), "dependencies": dependencies},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            template.delete()
        except ProtectedError:
            dependencies = get_template_dependencies(template)
            logger.warning(
                "Template deletion blocked by protected dependencies template_id=%s organization_id=%s dependencies=%s",
                template.id,
                template.organization_id,
                dependencies,
            )
            detail = (
                format_dependency_error(dependencies)
                if dependencies
                else "This template cannot be deleted because it is currently in use."
            )
            return Response(
                {"detail": detail, "dependencies": dependencies},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


def render_template_preview(template, parameters):
    text = template.body_text
    for index, value in enumerate(parameters or [], start=1):
        text = text.replace(f"{{{{{index}}}}}", str(value))
    return text


class SendMessageTemplateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, template_id):
        organization, templates = get_templates_for_user(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            template = templates.get(id=template_id)
        except MessageTemplate.DoesNotExist:
            return Response({"detail": "Template not found."}, status=status.HTTP_404_NOT_FOUND)

        if template.status != MessageTemplate.STATUS_APPROVED:
            return Response(
                {"detail": "Only approved templates can be sent."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SendTemplateSerializer(
            data=request.data,
            context={"organization": organization, "template": template},
        )
        serializer.is_valid(raise_exception=True)

        contact = Contact.objects.get(id=serializer.validated_data["contact_id"], organization=organization)
        conversation_id = serializer.validated_data.get("conversation_id")
        parameters = serializer.validated_data.get("parameters", [])

        if conversation_id:
            conversation = Conversation.objects.get(id=conversation_id, organization=organization)
            if conversation.contact_id != contact.id:
                return Response(
                    {"detail": "Conversation contact must match selected contact."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            conversation, _ = Conversation.objects.get_or_create(
                organization=organization,
                contact=contact,
                channel=Conversation.CHANNEL_WHATSAPP,
                status=Conversation.STATUS_OPEN,
            )

        message_text = render_template_preview(template, parameters)
        sent_at = timezone.now()
        config = WhatsAppBusinessConfig.objects.filter(organization=organization, is_active=True).first()

        try:
            send_result = send_whatsapp_template_message(
                config=config,
                to_phone_number=contact.phone_number,
                template_name=template.name,
                language=template.language,
                parameters=parameters,
            )
            message = Message.objects.create(
                organization=organization,
                conversation=conversation,
                sender_type=Message.SENDER_AGENT,
                direction=Message.DIRECTION_OUTBOUND,
                message_type=Message.TYPE_TEMPLATE,
                text=message_text,
                external_message_id=send_result.external_message_id,
                delivery_status=Message.DELIVERY_SENT,
                sent_at=sent_at,
            )
            response_status = status.HTTP_201_CREATED
            response_data = {"message": "Template sent.", "data": message}
        except WhatsAppSendError as send_error:
            message = Message.objects.create(
                organization=organization,
                conversation=conversation,
                sender_type=Message.SENDER_AGENT,
                direction=Message.DIRECTION_OUTBOUND,
                message_type=Message.TYPE_TEMPLATE,
                text=message_text,
                delivery_status=Message.DELIVERY_FAILED,
                sent_at=sent_at,
            )
            response_status = status.HTTP_502_BAD_GATEWAY
            response_data = {"detail": str(send_error), "data": message}

        conversation.last_message_at = message.sent_at or message.created_at
        conversation.save(update_fields=["last_message_at", "updated_at"])
        broadcast_inbox_event(
            organization.id,
            "message.created",
            conversation_id=conversation.id,
            message_id=message.id,
            contact_id=contact.id,
            delivery_status=message.delivery_status,
        )

        from conversations.serializers import MessageSerializer

        response_data["data"] = MessageSerializer(message).data
        response_data["conversation_id"] = conversation.id
        return Response(response_data, status=response_status)
