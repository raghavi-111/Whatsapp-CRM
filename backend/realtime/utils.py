from django.utils import timezone


def inbox_group_name(organization_id):
    return f"org_{organization_id}_inbox"


def broadcast_inbox_event(organization_id, event_type, **payload):
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    safe_payload = {
        "event_type": event_type,
        "timestamp": timezone.now().isoformat(),
        **payload,
    }
    async_to_sync(channel_layer.group_send)(
        inbox_group_name(organization_id),
        {
            "type": "inbox.event",
            "payload": safe_payload,
        },
    )
