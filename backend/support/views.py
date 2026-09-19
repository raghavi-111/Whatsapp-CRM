from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from contacts.models import Contact
from conversations.models import Conversation
from conversations.serializers import ConversationSerializer
from organizations.models import OrganizationMember
from realtime.utils import broadcast_inbox_event
from automations.models import AutomationRule
from automations.services import enqueue_automations

from .models import ContactNote, ConversationNote, Tag
from .serializers import ContactNoteSerializer, ConversationNoteSerializer, TagSerializer


def get_current_organization(user):
    membership = (
        OrganizationMember.objects.select_related("organization")
        .filter(user=user, status=OrganizationMember.STATUS_ACTIVE)
        .order_by("-joined_at")
        .first()
    )
    return membership.organization if membership else None


class TagListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(TagSerializer(Tag.objects.filter(organization=organization), many=True).data)

    def post(self, request):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = TagSerializer(data=request.data, context={"organization": organization})
        serializer.is_valid(raise_exception=True)
        tag = serializer.save(organization=organization)
        return Response(TagSerializer(tag).data, status=status.HTTP_201_CREATED)


class TagDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_tag(self, request, tag_id):
        organization = get_current_organization(request.user)
        if organization is None:
            return None, None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            return organization, Tag.objects.get(id=tag_id, organization=organization), None
        except Tag.DoesNotExist:
            return organization, None, Response({"detail": "Tag not found."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, tag_id):
        organization, tag, error_response = self.get_tag(request, tag_id)
        if error_response:
            return error_response
        serializer = TagSerializer(tag, data=request.data, partial=True, context={"organization": organization})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, tag_id):
        _, tag, error_response = self.get_tag(request, tag_id)
        if error_response:
            return error_response
        tag.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContactNotesView(APIView):
    permission_classes = [IsAuthenticated]

    def get_contact(self, request, contact_id):
        organization = get_current_organization(request.user)
        if organization is None:
            return None, None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            return organization, Contact.objects.get(id=contact_id, organization=organization), None
        except Contact.DoesNotExist:
            return organization, None, Response({"detail": "Contact not found."}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, contact_id):
        organization, contact, error_response = self.get_contact(request, contact_id)
        if error_response:
            return error_response
        notes = ContactNote.objects.filter(organization=organization, contact=contact)
        return Response(ContactNoteSerializer(notes, many=True).data)

    def post(self, request, contact_id):
        organization, contact, error_response = self.get_contact(request, contact_id)
        if error_response:
            return error_response
        serializer = ContactNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save(organization=organization, contact=contact, created_by=request.user)
        broadcast_inbox_event(
            organization.id,
            "contact.note_created",
            contact_id=contact.id,
        )
        return Response(ContactNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class ContactTagsView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, contact_id):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            contact = Contact.objects.get(id=contact_id, organization=organization)
        except Contact.DoesNotExist:
            return Response({"detail": "Contact not found."}, status=status.HTTP_404_NOT_FOUND)
        tag_ids = request.data.get("tag_ids", [])
        tags = Tag.objects.filter(id__in=tag_ids, organization=organization)
        if len(tag_ids) != tags.count():
            return Response({"detail": "One or more tags were not found."}, status=status.HTTP_400_BAD_REQUEST)
        previous_tag_ids = set(contact.tags.values_list("id", flat=True))
        contact.tags.set(tags)
        added_tags = [tag for tag in tags if tag.id not in previous_tag_ids]
        broadcast_inbox_event(
            organization.id,
            "contact.tags_updated",
            contact_id=contact.id,
        )
        for tag in added_tags:
            enqueue_automations(
                AutomationRule.TRIGGER_TAG_ADDED,
                organization,
                {"contact": contact, "tag": tag, "tag_name": tag.name},
            )
        from contacts.serializers import ContactSerializer

        return Response(ContactSerializer(contact).data)


class ConversationNotesView(APIView):
    permission_classes = [IsAuthenticated]

    def get_conversation(self, request, conversation_id):
        organization = get_current_organization(request.user)
        if organization is None:
            return None, None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            return organization, Conversation.objects.get(id=conversation_id, organization=organization), None
        except Conversation.DoesNotExist:
            return organization, None, Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, conversation_id):
        organization, conversation, error_response = self.get_conversation(request, conversation_id)
        if error_response:
            return error_response
        notes = ConversationNote.objects.filter(organization=organization, conversation=conversation)
        return Response(ConversationNoteSerializer(notes, many=True).data)

    def post(self, request, conversation_id):
        organization, conversation, error_response = self.get_conversation(request, conversation_id)
        if error_response:
            return error_response
        serializer = ConversationNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save(organization=organization, conversation=conversation, created_by=request.user)
        broadcast_inbox_event(
            organization.id,
            "conversation.note_created",
            conversation_id=conversation.id,
            contact_id=conversation.contact_id,
        )
        return Response(ConversationNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class ConversationAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, conversation_id):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            conversation = Conversation.objects.get(id=conversation_id, organization=organization)
        except Conversation.DoesNotExist:
            return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)
        assigned_to = request.data.get("assigned_to")
        if assigned_to in [None, ""]:
            conversation.assigned_to = None
        else:
            membership = OrganizationMember.objects.filter(
                organization=organization,
                user_id=assigned_to,
                status=OrganizationMember.STATUS_ACTIVE,
            ).first()
            if membership is None:
                return Response({"detail": "Assigned user must be an active organization member."}, status=400)
            conversation.assigned_to = membership.user
        conversation.save(update_fields=["assigned_to", "updated_at"])
        broadcast_inbox_event(
            organization.id,
            "conversation.assigned",
            conversation_id=conversation.id,
            contact_id=conversation.contact_id,
        )
        return Response(ConversationSerializer(conversation, context={"organization": organization}).data)


class ConversationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, conversation_id):
        organization = get_current_organization(request.user)
        if organization is None:
            return Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            conversation = Conversation.objects.get(id=conversation_id, organization=organization)
        except Conversation.DoesNotExist:
            return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)
        conversation_status = request.data.get("status")
        allowed_statuses = [choice[0] for choice in Conversation.STATUS_CHOICES]
        if conversation_status not in allowed_statuses:
            return Response({"detail": "Invalid conversation status."}, status=status.HTTP_400_BAD_REQUEST)
        previous_status = conversation.status
        conversation.status = conversation_status
        conversation.save(update_fields=["status", "updated_at"])
        broadcast_inbox_event(
            organization.id,
            "conversation.status_updated",
            conversation_id=conversation.id,
            contact_id=conversation.contact_id,
        )
        if previous_status != conversation_status:
            enqueue_automations(
                AutomationRule.TRIGGER_CONVERSATION_STATUS_CHANGED,
                organization,
                {
                    "contact": conversation.contact,
                    "conversation": conversation,
                    "previous_status": previous_status,
                    "conversation_status": conversation_status,
                },
            )
        return Response(ConversationSerializer(conversation, context={"organization": organization}).data)
