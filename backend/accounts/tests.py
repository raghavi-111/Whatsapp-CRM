from datetime import timedelta
import hashlib
import hmac
import json
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from unittest.mock import patch

from accounts.models import User
from automations.models import AutomationLog, AutomationRule
from automations.services import run_automations
from config.asgi import application
from contacts.models import Contact
from conversations.models import Conversation, Message
from organizations.models import OrganizationInvitation, OrganizationMember, create_organization_for_user
from support.models import ContactNote, Tag
from templates.models import MessageTemplate
from whatsapp.models import WhatsAppBusinessConfig


TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CHANNEL_LAYERS=TEST_CHANNEL_LAYERS,
    ALLOWED_HOSTS=["testserver", "localhost"],
)
class Phase20CoreTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@example.com", "testpass123")
        self.admin = User.objects.create_user("admin@example.com", "testpass123")
        self.agent = User.objects.create_user("agent@example.com", "testpass123")
        self.other_user = User.objects.create_user("other@example.com", "testpass123")
        self.organization = create_organization_for_user(self.owner, "Owner Org")
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.admin,
            role=OrganizationMember.ROLE_ADMIN,
            status=OrganizationMember.STATUS_ACTIVE,
        )
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.agent,
            role=OrganizationMember.ROLE_AGENT,
            status=OrganizationMember.STATUS_ACTIVE,
        )
        self.other_organization = create_organization_for_user(self.other_user, "Other Org")

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def create_invitation(self, email, role=OrganizationMember.ROLE_AGENT, **overrides):
        data = {
            "organization": self.organization,
            "email": email,
            "role": role,
            "invited_by": self.owner,
            "expires_at": timezone.now() + timedelta(days=7),
        }
        data.update(overrides)
        return OrganizationInvitation.objects.create(**data)

    def test_auth_register_login_and_me(self):
        register_response = self.client.post(
            "/api/auth/register/",
            {"email": "new@example.com", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(register_response.status_code, 201)
        self.assertIn("access", register_response.data)

        login_response = self.client.post(
            "/api/auth/login/",
            {"email": "new@example.com", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")
        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data["email"], "new@example.com")

    def test_public_auth_endpoints_ignore_invalid_bearer_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")

        register_response = self.client.post(
            "/api/auth/register/",
            {"email": "public-register@example.com", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(register_response.status_code, 201)
        self.assertIn("access", register_response.data)

        login_response = self.client.post(
            "/api/auth/login/",
            {"email": self.agent.email, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn("access", login_response.data)

    def test_expired_access_token_can_be_replaced_with_valid_refresh_token(self):
        access = AccessToken.for_user(self.agent)
        access.set_exp(lifetime=timedelta(seconds=-1))
        refresh = RefreshToken.for_user(self.agent)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        expired_response = self.client.get("/api/auth/me/")
        self.assertEqual(expired_response.status_code, 401)

        refresh_response = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": str(refresh)},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn("access", refresh_response.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh_response.data['access']}")
        retried_response = self.client.get("/api/auth/me/")
        self.assertEqual(retried_response.status_code, 200)
        self.assertEqual(retried_response.data["email"], self.agent.email)

    def test_expired_refresh_token_is_rejected(self):
        refresh = RefreshToken.for_user(self.agent)
        refresh.set_exp(lifetime=timedelta(seconds=-1))

        response = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": str(refresh)},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_organization_isolation_for_contacts(self):
        Contact.objects.create(
            organization=self.other_organization,
            phone_number="15550000001",
            full_name="Other Contact",
        )
        self.authenticate(self.owner)
        response = self.client.get("/api/contacts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_contacts_crud_and_agent_cannot_delete(self):
        self.authenticate(self.agent)
        create_response = self.client.post(
            "/api/contacts/",
            {"phone_number": "15550000002", "full_name": "Agent Contact"},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        contact_id = create_response.data["id"]

        patch_response = self.client.patch(
            f"/api/contacts/{contact_id}/",
            {"company_name": "Acme"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)

        delete_response = self.client.delete(f"/api/contacts/{contact_id}/")
        self.assertEqual(delete_response.status_code, 403)

        self.authenticate(self.owner)
        owner_delete_response = self.client.delete(f"/api/contacts/{contact_id}/")
        self.assertEqual(owner_delete_response.status_code, 204)

    def test_agent_can_create_contact_note(self):
        contact = Contact.objects.create(
            organization=self.organization,
            phone_number="15550000007",
            full_name="Note Contact",
        )

        self.authenticate(self.agent)
        response = self.client.post(
            f"/api/contacts/{contact.id}/notes/",
            {"note": "Follow up tomorrow"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            ContactNote.objects.filter(
                organization=self.organization,
                contact=contact,
                created_by=self.agent,
                note="Follow up tomorrow",
            ).exists()
        )

    def test_conversations_and_messages(self):
        contact = Contact.objects.create(organization=self.organization, phone_number="15550000003")
        self.authenticate(self.agent)
        conversation_response = self.client.post(
            "/api/conversations/",
            {"contact": contact.id, "status": "open"},
            format="json",
        )
        self.assertEqual(conversation_response.status_code, 201)
        conversation_id = conversation_response.data["id"]

        message_response = self.client.post(
            f"/api/conversations/{conversation_id}/messages/",
            {"text": "Hello", "message_type": "text"},
            format="json",
        )
        self.assertIn(message_response.status_code, [201, 502])
        self.assertTrue(Message.objects.filter(conversation_id=conversation_id, text="Hello").exists())

    @patch.dict("os.environ", {"WHATSAPP_SEND_MODE": "mock"}, clear=False)
    def test_mock_outbound_text_succeeds_without_whatsapp_config(self):
        contact = Contact.objects.create(organization=self.organization, phone_number="15550000006")
        conversation = Conversation.objects.create(organization=self.organization, contact=contact)

        self.authenticate(self.agent)
        response = self.client.post(
            f"/api/conversations/{conversation.id}/messages/",
            {"text": "Hello from mock mode", "message_type": "text"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["delivery_status"], Message.DELIVERY_SENT)
        self.assertTrue(response.data["external_message_id"].startswith("mock-wamid-"))
        self.assertTrue(
            Message.objects.filter(
                conversation=conversation,
                text="Hello from mock mode",
                delivery_status=Message.DELIVERY_SENT,
                external_message_id__startswith="mock-wamid-",
            ).exists()
        )

    def test_whatsapp_config_masks_secrets(self):
        self.authenticate(self.owner)
        response = self.client.post(
            "/api/whatsapp/config/",
            {
                "phone_number_id": "phone-id",
                "whatsapp_business_account_id": "waba-id",
                "meta_app_secret": "super-secret-app",
                "access_token": "super-secret-token",
                "webhook_verify_token": "super-secret-verify",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("access_token", response.data)
        self.assertNotIn("meta_app_secret", response.data)
        self.assertEqual(response.data["access_token_masked"], "****oken")
        self.assertEqual(response.data["meta_app_secret_masked"], "****-app")
        self.assertEqual(response.data["webhook_verify_token_masked"], "****rify")

    def test_webhook_verification(self):
        WhatsAppBusinessConfig.objects.create(
            organization=self.organization,
            phone_number_id="phone-id",
            whatsapp_business_account_id="waba-id",
            meta_app_secret="app-secret",
            access_token="access-token",
            webhook_verify_token="verify-token",
        )
        response = self.client.get(
            "/api/whatsapp/webhook/",
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-token",
                "hub.challenge": "challenge-value",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "challenge-value")

    def test_inbound_webhook_text_creates_contact_conversation_message(self):
        WhatsAppBusinessConfig.objects.create(
            organization=self.organization,
            phone_number_id="phone-id",
            whatsapp_business_account_id="waba-id",
            meta_app_secret="app-secret",
            access_token="access-token",
            webhook_verify_token="verify-token",
        )
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "phone-id"},
                                "contacts": [{"wa_id": "15550000004", "profile": {"name": "Webhook User"}}],
                                "messages": [
                                    {
                                        "id": "wamid-test-1",
                                        "from": "15550000004",
                                        "timestamp": "1735689600",
                                        "type": "text",
                                        "text": {"body": "Price please"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
        response = self.client.post(
            "/api/whatsapp/webhook/",
            body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Contact.objects.filter(organization=self.organization, phone_number="15550000004").exists())
        self.assertTrue(Message.objects.filter(organization=self.organization, external_message_id="wamid-test-1").exists())

    def test_automation_basic_execution(self):
        contact = Contact.objects.create(organization=self.organization, phone_number="15550000005")
        conversation = Conversation.objects.create(organization=self.organization, contact=contact)
        message = Message.objects.create(
            organization=self.organization,
            conversation=conversation,
            sender_type=Message.SENDER_CONTACT,
            direction=Message.DIRECTION_INBOUND,
            message_type=Message.TYPE_TEXT,
            text="I need price",
        )
        AutomationRule.objects.create(
            organization=self.organization,
            name="Tag price leads",
            trigger_type=AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED,
            conditions_json=[{"field": "message_text_contains", "operator": "contains", "value": "price"}],
            actions_json=[{"type": "add_tag", "tag_name": "Price Enquiry"}],
            created_by=self.owner,
        )
        run_automations(
            AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED,
            self.organization,
            {"contact": contact, "conversation": conversation, "message": message},
        )
        self.assertTrue(Tag.objects.filter(organization=self.organization, name="Price Enquiry", contacts=contact).exists())
        self.assertTrue(AutomationLog.objects.filter(organization=self.organization, status=AutomationLog.STATUS_SUCCESS).exists())

    def test_owner_can_create_automation_successfully(self):
        self.authenticate(self.owner)
        response = self.client.post(
            "/api/automations/",
            {
                "name": "Price enquiry triage",
                "description": "Tag price leads and mark pending.",
                "trigger_type": AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED,
                "conditions_json": [
                    {"field": "message_text_contains", "operator": "contains", "value": "price"}
                ],
                "actions_json": [
                    {"type": "add_tag", "tag_name": "Price Enquiry"},
                    {"type": "update_conversation_status", "status": "pending"},
                    {
                        "type": "send_message",
                        "text": "Thank you for your enquiry. Our sales team will contact you shortly.",
                    },
                ],
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            AutomationRule.objects.filter(
                organization=self.organization,
                name="Price enquiry triage",
                created_by=self.owner,
            ).exists()
        )

    def test_automation_create_requires_jwt(self):
        response = self.client.post(
            "/api/automations/",
            {
                "name": "Unauthenticated automation",
                "trigger_type": AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED,
                "conditions_json": [],
                "actions_json": [],
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_invalid_automation_condition_schema_returns_clear_400(self):
        self.authenticate(self.owner)
        response = self.client.post(
            "/api/automations/",
            {
                "name": "Broken automation",
                "trigger_type": AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED,
                "conditions_json": [{"field": "unsupported_field", "operator": "equals", "value": "x"}],
                "actions_json": [{"type": "add_tag", "tag_name": "Lead"}],
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("conditions_json", response.data)
        self.assertIn("unsupported field", str(response.data["conditions_json"]).lower())

    def test_frontend_example_automation_json_creates_successfully(self):
        self.authenticate(self.owner)
        condition_example = [
            {
                "field": "message_text_contains",
                "operator": "contains",
                "value": "price",
            }
        ]
        action_example = [
            {
                "type": "add_tag",
                "tag_name": "Price Enquiry",
            },
            {
                "type": "update_conversation_status",
                "status": "pending",
            },
            {
                "type": "send_message",
                "text": "Thank you for your enquiry. Our sales team will contact you shortly.",
            },
        ]

        response = self.client.post(
            "/api/automations/",
            {
                "name": "Frontend example",
                "trigger_type": AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED,
                "conditions_json": condition_example,
                "actions_json": action_example,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["conditions_json"], condition_example)
        self.assertEqual(response.data["actions_json"], action_example)

    def test_agent_cannot_manage_automations(self):
        self.authenticate(self.agent)
        response = self.client.post(
            "/api/automations/",
            {
                "name": "Agent automation",
                "trigger_type": AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED,
                "conditions_json": [],
                "actions_json": [],
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_developer_simulate_inbound_message_runs_automation(self):
        contact = Contact.objects.create(organization=self.organization, phone_number="15550000008")
        conversation = Conversation.objects.create(
            organization=self.organization,
            contact=contact,
            status=Conversation.STATUS_OPEN,
        )
        AutomationRule.objects.create(
            organization=self.organization,
            name="Price simulation",
            trigger_type=AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED,
            conditions_json=[
                {"field": "message_text_contains", "operator": "contains", "value": "price"}
            ],
            actions_json=[
                {"type": "add_tag", "tag_name": "Price Enquiry"},
                {"type": "update_conversation_status", "status": "pending"},
            ],
            created_by=self.owner,
        )

        self.authenticate(self.owner)
        response = self.client.post(
            "/api/automations/simulate-inbound/",
            {"conversation_id": conversation.id, "text": "what is the price?"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Message.objects.filter(
                organization=self.organization,
                conversation=conversation,
                direction=Message.DIRECTION_INBOUND,
                sender_type=Message.SENDER_CONTACT,
                message_type=Message.TYPE_TEXT,
                delivery_status=Message.DELIVERY_DELIVERED,
                text="what is the price?",
            ).exists()
        )
        self.assertTrue(Tag.objects.filter(organization=self.organization, name="Price Enquiry", contacts=contact).exists())
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.STATUS_PENDING)
        self.assertTrue(
            AutomationLog.objects.filter(
                organization=self.organization,
                trigger_type=AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED,
                status=AutomationLog.STATUS_SUCCESS,
            ).exists()
        )

    @patch.dict("os.environ", {"WHATSAPP_SEND_MODE": "mock"}, clear=False)
    def test_send_message_automation_action_creates_mock_outbound_reply(self):
        contact = Contact.objects.create(organization=self.organization, phone_number="15550000009")
        conversation = Conversation.objects.create(organization=self.organization, contact=contact)
        inbound_message = Message.objects.create(
            organization=self.organization,
            conversation=conversation,
            sender_type=Message.SENDER_CONTACT,
            direction=Message.DIRECTION_INBOUND,
            message_type=Message.TYPE_TEXT,
            text="what is the price?",
            delivery_status=Message.DELIVERY_DELIVERED,
        )
        reply_text = "Thank you for your enquiry. Our sales team will contact you shortly."
        AutomationRule.objects.create(
            organization=self.organization,
            name="Auto reply price leads",
            trigger_type=AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED,
            conditions_json=[{"field": "message_text_contains", "operator": "contains", "value": "price"}],
            actions_json=[
                {"type": "add_tag", "tag_name": "Price Enquiry"},
                {"type": "update_conversation_status", "status": "pending"},
                {"type": "send_message", "text": reply_text},
            ],
            created_by=self.owner,
        )

        run_automations(
            AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED,
            self.organization,
            {"contact": contact, "conversation": conversation, "message": inbound_message},
        )

        outbound = Message.objects.get(
            organization=self.organization,
            conversation=conversation,
            direction=Message.DIRECTION_OUTBOUND,
            message_type=Message.TYPE_TEXT,
            text=reply_text,
        )
        self.assertEqual(outbound.sender_type, Message.SENDER_SYSTEM)
        self.assertEqual(outbound.delivery_status, Message.DELIVERY_SENT)
        self.assertTrue(outbound.external_message_id.startswith("mock-wamid-"))
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, Conversation.STATUS_PENDING)
        self.assertTrue(Tag.objects.filter(organization=self.organization, name="Price Enquiry", contacts=contact).exists())
        self.assertTrue(
            AutomationLog.objects.filter(
                organization=self.organization,
                status=AutomationLog.STATUS_SUCCESS,
                message__contains="Actions executed: 3",
            ).exists()
        )

    def test_role_permissions_owner_admin_agent(self):
        self.authenticate(self.owner)
        owner_template_response = self.client.post(
            "/api/templates/",
            {
                "name": "hello_world",
                "language": "en_us",
                "category": "utility",
                "status": MessageTemplate.STATUS_DRAFT,
                "body_text": "Hello",
            },
            format="json",
        )
        self.assertEqual(owner_template_response.status_code, 201)

        self.authenticate(self.admin)
        admin_invite_agent = self.client.post(
            "/api/organizations/invitations/",
            {"email": "invite-agent@example.com", "role": "agent"},
            format="json",
        )
        self.assertEqual(admin_invite_agent.status_code, 201)
        admin_invite_admin = self.client.post(
            "/api/organizations/invitations/",
            {"email": "invite-admin@example.com", "role": "admin"},
            format="json",
        )
        self.assertEqual(admin_invite_admin.status_code, 403)

        self.authenticate(self.agent)
        agent_template_response = self.client.post(
            "/api/templates/",
            {
                "name": "agent_template",
                "language": "en_us",
                "category": "utility",
                "status": MessageTemplate.STATUS_DRAFT,
                "body_text": "Hello",
            },
            format="json",
        )
        self.assertEqual(agent_template_response.status_code, 403)
        team_response = self.client.get("/api/organizations/members/")
        self.assertEqual(team_response.status_code, 403)

    def test_successful_agent_invitation_acceptance_enters_invited_organization(self):
        register_response = self.client.post(
            "/api/auth/register/",
            {"email": "new-agent@example.com", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(register_response.status_code, 201)
        invitation = self.create_invitation("new-agent@example.com", OrganizationMember.ROLE_AGENT)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {register_response.data['access']}")
        accept_response = self.client.post(f"/api/organizations/invitations/{invitation.token}/accept/")

        self.assertEqual(accept_response.status_code, 200)
        membership = OrganizationMember.objects.get(organization=self.organization, user__email="new-agent@example.com")
        self.assertEqual(membership.role, OrganizationMember.ROLE_AGENT)
        self.assertEqual(membership.status, OrganizationMember.STATUS_ACTIVE)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.STATUS_ACCEPTED)

        current_response = self.client.get("/api/organizations/current/")
        self.assertEqual(current_response.status_code, 200)
        self.assertEqual(current_response.data["id"], self.organization.id)

    def test_successful_admin_invitation_acceptance_and_permissions(self):
        invited_admin = User.objects.create_user("accepted-admin@example.com", "testpass123")
        invitation = self.create_invitation("accepted-admin@example.com", OrganizationMember.ROLE_ADMIN)

        self.authenticate(invited_admin)
        accept_response = self.client.post(f"/api/organizations/invitations/{invitation.token}/accept/")
        self.assertEqual(accept_response.status_code, 200)

        invite_agent_response = self.client.post(
            "/api/organizations/invitations/",
            {"email": "admin-can-invite-agent@example.com", "role": "agent"},
            format="json",
        )
        self.assertEqual(invite_agent_response.status_code, 201)

        invite_admin_response = self.client.post(
            "/api/organizations/invitations/",
            {"email": "admin-cannot-invite-admin@example.com", "role": "admin"},
            format="json",
        )
        self.assertEqual(invite_admin_response.status_code, 403)

    def test_wrong_email_cannot_accept_invitation(self):
        invited_user = User.objects.create_user("right-email@example.com", "testpass123")
        wrong_user = User.objects.create_user("wrong-email@example.com", "testpass123")
        invitation = self.create_invitation(invited_user.email, OrganizationMember.ROLE_AGENT)

        self.authenticate(wrong_user)
        response = self.client.post(f"/api/organizations/invitations/{invitation.token}/accept/")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(OrganizationMember.objects.filter(organization=self.organization, user=wrong_user).exists())

    def test_expired_invitation_cannot_be_accepted(self):
        invited_user = User.objects.create_user("expired-agent@example.com", "testpass123")
        invitation = self.create_invitation(
            invited_user.email,
            OrganizationMember.ROLE_AGENT,
            expires_at=timezone.now() - timedelta(days=1),
        )

        self.authenticate(invited_user)
        response = self.client.post(f"/api/organizations/invitations/{invitation.token}/accept/")
        self.assertEqual(response.status_code, 400)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, OrganizationInvitation.STATUS_EXPIRED)

    def test_cancelled_invitation_cannot_be_accepted(self):
        invited_user = User.objects.create_user("cancelled-agent@example.com", "testpass123")
        invitation = self.create_invitation(
            invited_user.email,
            OrganizationMember.ROLE_AGENT,
            status=OrganizationInvitation.STATUS_CANCELLED,
        )

        self.authenticate(invited_user)
        response = self.client.post(f"/api/organizations/invitations/{invitation.token}/accept/")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(OrganizationMember.objects.filter(organization=self.organization, user=invited_user).exists())

    def test_invitation_cannot_be_accepted_twice(self):
        invited_user = User.objects.create_user("twice-agent@example.com", "testpass123")
        invitation = self.create_invitation(invited_user.email, OrganizationMember.ROLE_AGENT)

        self.authenticate(invited_user)
        first_response = self.client.post(f"/api/organizations/invitations/{invitation.token}/accept/")
        second_response = self.client.post(f"/api/organizations/invitations/{invitation.token}/accept/")
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(
            OrganizationMember.objects.filter(organization=self.organization, user=invited_user).count(),
            1,
        )

    def test_unauthenticated_invitation_acceptance_requires_login_and_preserves_preview(self):
        invitation = self.create_invitation("needs-login@example.com", OrganizationMember.ROLE_AGENT)

        preview_response = self.client.get(f"/api/organizations/invitations/{invitation.token}/")
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.data["email"], "needs-login@example.com")

        accept_response = self.client.post(f"/api/organizations/invitations/{invitation.token}/accept/")
        self.assertEqual(accept_response.status_code, 401)

    def test_accepted_member_appears_in_team_members_list(self):
        invited_user = User.objects.create_user("listed-agent@example.com", "testpass123")
        invitation = self.create_invitation(invited_user.email, OrganizationMember.ROLE_AGENT)

        self.authenticate(invited_user)
        self.assertEqual(self.client.post(f"/api/organizations/invitations/{invitation.token}/accept/").status_code, 200)

        self.authenticate(self.owner)
        members_response = self.client.get("/api/organizations/members/")
        self.assertEqual(members_response.status_code, 200)
        self.assertIn("listed-agent@example.com", [member["email"] for member in members_response.data])

    def test_accepted_agent_role_permissions_are_enforced(self):
        invited_user = User.objects.create_user("accepted-agent@example.com", "testpass123")
        invitation = self.create_invitation(invited_user.email, OrganizationMember.ROLE_AGENT)

        self.authenticate(invited_user)
        self.assertEqual(self.client.post(f"/api/organizations/invitations/{invitation.token}/accept/").status_code, 200)

        template_response = self.client.post(
            "/api/templates/",
            {
                "name": "accepted_agent_template",
                "language": "en_us",
                "category": "utility",
                "status": MessageTemplate.STATUS_DRAFT,
                "body_text": "Hello",
            },
            format="json",
        )
        self.assertEqual(template_response.status_code, 403)

    def test_crm_apis_require_auth_except_webhook(self):
        protected_paths = [
            "/api/contacts/",
            "/api/conversations/",
            "/api/templates/",
            "/api/automations/",
            "/api/analytics/summary/",
            "/api/organizations/current/",
        ]
        for path in protected_paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 401, path)

        webhook_response = self.client.post("/api/whatsapp/webhook/", {}, format="json")
        self.assertEqual(webhook_response.status_code, 403)

    def test_message_analytics_respects_days_query_parameter(self):
        contact = Contact.objects.create(
            organization=self.organization,
            phone_number="15550000999",
            full_name="Analytics Contact",
        )
        conversation = Conversation.objects.create(
            organization=self.organization,
            contact=contact,
            status=Conversation.STATUS_OPEN,
        )
        recent_message = Message.objects.create(
            organization=self.organization,
            conversation=conversation,
            sender_type=Message.SENDER_CONTACT,
            direction=Message.DIRECTION_INBOUND,
            text="Recent",
        )
        older_message = Message.objects.create(
            organization=self.organization,
            conversation=conversation,
            sender_type=Message.SENDER_AGENT,
            direction=Message.DIRECTION_OUTBOUND,
            text="Older",
        )
        Message.objects.filter(pk=recent_message.pk).update(created_at=timezone.now() - timedelta(days=2))
        Message.objects.filter(pk=older_message.pk).update(created_at=timezone.now() - timedelta(days=20))

        self.authenticate(self.owner)
        seven_day_response = self.client.get("/api/analytics/messages/?days=7")
        thirty_day_response = self.client.get("/api/analytics/messages/?days=30")

        self.assertEqual(seven_day_response.status_code, 200)
        self.assertEqual(thirty_day_response.status_code, 200)
        self.assertEqual(seven_day_response.data["days"], 7)
        self.assertEqual(thirty_day_response.data["days"], 30)
        self.assertEqual(len(seven_day_response.data["daily_by_direction"]), 7)
        self.assertEqual(len(thirty_day_response.data["daily_by_direction"]), 30)
        self.assertEqual(sum(item["total"] for item in seven_day_response.data["daily_by_direction"]), 1)
        self.assertEqual(sum(item["total"] for item in thirty_day_response.data["daily_by_direction"]), 2)

    def test_inbox_websocket_connects_with_valid_jwt(self):
        async def connect():
            token = str(AccessToken.for_user(self.agent))
            communicator = WebsocketCommunicator(application, f"/ws/inbox/?token={token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            message = await communicator.receive_json_from()
            self.assertEqual(message["event_type"], "connected")
            await communicator.disconnect()

        async_to_sync(connect)()

    def test_inbox_websocket_rejects_missing_token(self):
        async def connect():
            communicator = WebsocketCommunicator(application, "/ws/inbox/")
            connected, _ = await communicator.connect()
            self.assertFalse(connected)
            await communicator.disconnect()

        async_to_sync(connect)()
