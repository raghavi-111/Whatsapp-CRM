from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from contacts.models import Contact
from conversations.models import Message
from organizations.models import create_organization_for_user
from templates.models import MessageTemplate
from whatsapp.sending import WhatsAppSendError

from .models import BroadcastCampaign, BroadcastRecipient
from .services import create_recipients_for_campaign, send_campaign_now, update_recipient_from_webhook


class BroadcastHardeningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("broadcast-owner@example.com", "pass1234")
        self.organization = create_organization_for_user(self.user, "Broadcast Org")
        self.other_user = User.objects.create_user("broadcast-other@example.com", "pass1234")
        self.other_organization = create_organization_for_user(self.other_user, "Other Broadcast Org")
        self.template = MessageTemplate.objects.create(
            organization=self.organization,
            name="notice",
            language="en_US",
            status=MessageTemplate.STATUS_APPROVED,
            body_text="Hello {{1}}",
        )
        self.contact = Contact.objects.create(
            organization=self.organization,
            full_name="Alice",
            phone_number="15550001000",
        )
        self.campaign = BroadcastCampaign.objects.create(
            organization=self.organization,
            created_by=self.user,
            name="One recipient",
            template=self.template,
            template_language="en_US",
            variable_mappings=[{"type": "contact_name"}],
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_campaign_api_hides_other_organization(self):
        other_template = MessageTemplate.objects.create(
            organization=self.other_organization,
            name="other",
            language="en_US",
            status=MessageTemplate.STATUS_APPROVED,
            body_text="Other",
        )
        foreign = BroadcastCampaign.objects.create(
            organization=self.other_organization,
            name="Hidden",
            template=other_template,
            template_language="en_US",
        )
        self.assertEqual(self.client.get(f"/api/broadcasts/campaigns/{foreign.id}/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/broadcasts/campaigns/{foreign.id}/send-now/").status_code, 404)

    def test_recipient_creation_is_idempotent(self):
        first = create_recipients_for_campaign(self.campaign)
        second = create_recipients_for_campaign(self.campaign)
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(BroadcastRecipient.objects.filter(campaign=self.campaign).count(), 1)

    @patch("automations.services.enqueue_automations")
    @patch("broadcasts.services.broadcast_inbox_event")
    @patch("broadcasts.services.send_whatsapp_template_message")
    def test_one_recipient_mocked_send_succeeds_once(self, send_mock, _event_mock, _automation_mock):
        send_mock.return_value = SimpleNamespace(external_message_id="wamid.broadcast.1")
        result = send_campaign_now(self.campaign)
        self.assertEqual(result.status, BroadcastCampaign.STATUS_COMPLETED)
        self.assertEqual(result.sent_count, 1)
        self.assertEqual(Message.objects.filter(organization=self.organization).count(), 1)
        send_mock.assert_called_once()
        with self.assertRaisesRegex(ValueError, "already started"):
            send_campaign_now(self.campaign)
        send_mock.assert_called_once()

    @patch("broadcasts.services.broadcast_inbox_event")
    @patch("broadcasts.services.send_whatsapp_template_message", side_effect=WhatsAppSendError("safe failure"))
    def test_send_failure_is_recorded_without_success_message(self, _send_mock, _event_mock):
        result = send_campaign_now(self.campaign)
        recipient = BroadcastRecipient.objects.get(campaign=self.campaign)
        self.assertEqual(result.status, BroadcastCampaign.STATUS_FAILED)
        self.assertEqual(recipient.status, BroadcastRecipient.STATUS_FAILED)
        self.assertEqual(recipient.error_message, "safe failure")
        self.assertFalse(Message.objects.filter(organization=self.organization).exists())

    def test_status_update_is_org_scoped_and_does_not_regress_from_read(self):
        recipient = BroadcastRecipient.objects.create(
            campaign=self.campaign,
            contact=self.contact,
            phone=self.contact.phone_number,
            status=BroadcastRecipient.STATUS_READ,
            whatsapp_message_id="wamid.shared",
        )
        self.assertIsNone(
            update_recipient_from_webhook(
                "wamid.shared", Message.DELIVERY_FAILED, organization=self.other_organization
            )
        )
        update_recipient_from_webhook(
            "wamid.shared", Message.DELIVERY_DELIVERED, organization=self.organization
        )
        recipient.refresh_from_db()
        self.assertEqual(recipient.status, BroadcastRecipient.STATUS_READ)
