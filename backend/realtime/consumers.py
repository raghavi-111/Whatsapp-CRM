from urllib.parse import parse_qs
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from organizations.models import OrganizationMember

from .utils import inbox_group_name


logger = logging.getLogger(__name__)


class InboxConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        token = self.get_token()
        user_and_org, reject_reason = await self.get_user_and_organization(token)

        if user_and_org is None:
            logger.warning("Inbox WebSocket rejected reason=%s", reject_reason)
            await self.close(code=4401)
            return

        self.user, self.organization_id = user_and_org
        self.group_name = inbox_group_name(self.organization_id)

        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        except Exception:
            logger.exception(
                "Inbox WebSocket rejected reason=channel_layer_error user_id=%s organization_id=%s",
                self.user.id,
                self.organization_id,
            )
            await self.close(code=1011)
            return

        await self.accept()
        await self.send_json({"event_type": "connected"})

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def inbox_event(self, event):
        await self.send_json(event["payload"])

    def get_token(self):
        query_string = self.scope.get("query_string", b"").decode()
        return parse_qs(query_string).get("token", [None])[0]

    @database_sync_to_async
    def get_user_and_organization(self, token):
        if not token:
            return None, "missing_token"

        try:
            access_token = AccessToken(token)
        except TokenError as error:
            message = str(error).lower()
            if "expired" in message:
                return None, "expired_token"
            return None, "invalid_token"
        except InvalidToken:
            return None, "invalid_token"
        except Exception:
            logger.exception("Inbox WebSocket token decode exception")
            return None, "exception"

        user_id = access_token.get("user_id")
        if not user_id:
            return None, "invalid_token"

        User = get_user_model()

        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return None, "user_not_found"
        except Exception:
            logger.exception("Inbox WebSocket user lookup exception user_id=%s", user_id)
            return None, "exception"

        try:
            membership = (
                OrganizationMember.objects.filter(
                    user=user,
                    status=OrganizationMember.STATUS_ACTIVE,
                )
                .order_by("-joined_at")
                .first()
            )
        except Exception:
            logger.exception("Inbox WebSocket organization lookup exception user_id=%s", user.id)
            return None, "exception"

        if membership is None:
            return None, "no_active_organization"

        return (user, membership.organization_id), None
