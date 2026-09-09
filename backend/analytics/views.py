from datetime import datetime, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from automations.models import AutomationLog
from contacts.models import Contact
from conversations.models import Conversation, Message
from organizations.models import OrganizationMember


def get_current_organization(user):
    membership = (
        OrganizationMember.objects.select_related("organization")
        .filter(user=user, status=OrganizationMember.STATUS_ACTIVE)
        .order_by("-joined_at")
        .first()
    )
    return membership.organization if membership else None


def organization_or_error(user):
    organization = get_current_organization(user)
    if organization is None:
        return None, Response({"detail": "No active organization found."}, status=status.HTTP_404_NOT_FOUND)
    return organization, None


def counts_by(queryset, field_name):
    return {
        row[field_name]: row["count"]
        for row in queryset.values(field_name).annotate(count=Count("id")).order_by(field_name)
    }


def range_days(request):
    try:
        days = int(request.query_params.get("days", 7))
    except (TypeError, ValueError):
        return 7
    return days if days in {7, 30, 90} else 7


def last_n_days(days):
    today = timezone.localdate()
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def daily_counts(queryset, date_field, days=7):
    date_range = last_n_days(days)
    start = timezone.make_aware(datetime.combine(date_range[0], datetime.min.time()))
    rows = (
        queryset.filter(**{f"{date_field}__gte": start})
        .annotate(day=TruncDate(date_field))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    counts = {row["day"]: row["count"] for row in rows}
    return [{"date": day.isoformat(), "count": counts.get(day, 0)} for day in date_range]


def daily_message_direction_counts(queryset, days=7):
    date_range = last_n_days(days)
    start = timezone.make_aware(datetime.combine(date_range[0], datetime.min.time()))
    rows = (
        queryset.filter(created_at__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day", "direction")
        .annotate(count=Count("id"))
        .order_by("day", "direction")
    )
    counts = {(row["day"], row["direction"]): row["count"] for row in rows}
    return [
        {
            "date": day.isoformat(),
            "inbound": counts.get((day, Message.DIRECTION_INBOUND), 0),
            "outbound": counts.get((day, Message.DIRECTION_OUTBOUND), 0),
            "total": counts.get((day, Message.DIRECTION_INBOUND), 0)
            + counts.get((day, Message.DIRECTION_OUTBOUND), 0),
        }
        for day in date_range
    ]


class SummaryAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = organization_or_error(request.user)
        if error_response:
            return error_response

        today = timezone.localdate()
        contacts = Contact.objects.filter(organization=organization)
        conversations = Conversation.objects.filter(organization=organization)
        messages_today = Message.objects.filter(organization=organization, created_at__date=today)
        automation_logs_today = AutomationLog.objects.filter(organization=organization, created_at__date=today)

        return Response(
            {
                "total_contacts": contacts.count(),
                "active_contacts": contacts.filter(status=Contact.STATUS_ACTIVE).count(),
                "open_conversations": conversations.filter(status=Conversation.STATUS_OPEN).count(),
                "pending_conversations": conversations.filter(status=Conversation.STATUS_PENDING).count(),
                "resolved_conversations": conversations.filter(status=Conversation.STATUS_RESOLVED).count(),
                "inbound_messages_today": messages_today.filter(direction=Message.DIRECTION_INBOUND).count(),
                "outbound_messages_today": messages_today.filter(direction=Message.DIRECTION_OUTBOUND).count(),
                "failed_messages_today": messages_today.filter(delivery_status=Message.DELIVERY_FAILED).count(),
                "automations_success_today": automation_logs_today.filter(status=AutomationLog.STATUS_SUCCESS).count(),
                "automations_failed_today": automation_logs_today.filter(status=AutomationLog.STATUS_FAILED).count(),
            }
        )


class MessagesAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = organization_or_error(request.user)
        if error_response:
            return error_response

        days = range_days(request)
        messages = Message.objects.filter(organization=organization)
        return Response(
            {
                "days": days,
                "by_direction": counts_by(messages, "direction"),
                "by_message_type": counts_by(messages, "message_type"),
                "by_delivery_status": counts_by(messages, "delivery_status"),
                "daily_last_7_days": daily_counts(messages, "created_at"),
                "daily_range": daily_counts(messages, "created_at", days),
                "daily_by_direction": daily_message_direction_counts(messages, days),
            }
        )


class ConversationsAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = organization_or_error(request.user)
        if error_response:
            return error_response

        conversations = Conversation.objects.filter(organization=organization)
        return Response(
            {
                "by_status": counts_by(conversations, "status"),
                "assignment": {
                    "assigned": conversations.filter(assigned_to__isnull=False).count(),
                    "unassigned": conversations.filter(assigned_to__isnull=True).count(),
                },
                "new_daily_last_7_days": daily_counts(conversations, "created_at"),
            }
        )


class AgentsAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = organization_or_error(request.user)
        if error_response:
            return error_response

        members = OrganizationMember.objects.select_related("user").filter(
            organization=organization,
            status=OrganizationMember.STATUS_ACTIVE,
        )
        conversations = Conversation.objects.filter(organization=organization)
        outbound_agent_messages = Message.objects.filter(
            organization=organization,
            sender_type=Message.SENDER_AGENT,
            direction=Message.DIRECTION_OUTBOUND,
        ).count()

        rows = []
        for membership in members:
            rows.append(
                {
                    "user_id": membership.user_id,
                    "email": membership.user.email,
                    "role": membership.role,
                    "assigned_conversations": conversations.filter(assigned_to=membership.user).count(),
                    "messages_sent": None,
                }
            )

        return Response(
            {
                "agents": rows,
                "unassigned_conversations": conversations.filter(assigned_to__isnull=True).count(),
                "organization_outbound_agent_messages": outbound_agent_messages,
                "messages_sent_note": "Per-agent message counts are unavailable until outbound messages store the sending user.",
            }
        )


class AutomationsAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error_response = organization_or_error(request.user)
        if error_response:
            return error_response

        logs = AutomationLog.objects.select_related("rule").filter(organization=organization)
        latest_failed_logs = logs.filter(status=AutomationLog.STATUS_FAILED).order_by("-created_at")[:10]
        return Response(
            {
                "by_status": counts_by(logs, "status"),
                "latest_failed_logs": [
                    {
                        "id": log.id,
                        "rule_id": log.rule_id,
                        "rule_name": log.rule.name if log.rule else "Deleted rule",
                        "trigger_type": log.trigger_type,
                        "message": log.message,
                        "created_at": log.created_at,
                    }
                    for log in latest_failed_logs
                ],
            }
        )
