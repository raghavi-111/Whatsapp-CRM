from types import SimpleNamespace
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import User
from automations.models import AutomationRule
from broadcasts.models import BroadcastCampaign
from contacts.models import Contact
from conversations.models import Message
from flows.models import CustomerFlow
from organizations.models import create_organization_for_user
from whatsapp.sending import WhatsAppSendError

from .models import MessageTemplate


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class TemplateApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user("template-owner@example.com", "testpass123")
        self.organization = create_organization_for_user(self.owner, "Template Org")
        self.other_owner = User.objects.create_user("other-template-owner@example.com", "testpass123")
        self.other_organization = create_organization_for_user(self.other_owner, "Other Template Org")
        self.client.force_authenticate(user=self.owner)

    def create_template(self, **overrides):
        values = {
            "organization": self.organization,
            "created_by": self.owner,
            "name": "order_update",
            "language": "en_us",
            "body_text": "Hello {{1}}",
            "status": MessageTemplate.STATUS_APPROVED,
        }
        values.update(overrides)
        return MessageTemplate.objects.create(**values)

    def test_successful_delete_and_duplicate_delete(self):
        template = self.create_template()

        response = self.client.delete(f"/api/templates/{template.id}/")
        duplicate_response = self.client.delete(f"/api/templates/{template.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(duplicate_response.status_code, 404)
        self.assertFalse(MessageTemplate.objects.filter(id=template.id).exists())

    def test_delete_nonexistent_template(self):
        response = self.client.delete("/api/templates/999999/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Template not found.")

    def test_cross_organization_delete_is_hidden(self):
        template = self.create_template(
            organization=self.other_organization,
            created_by=self.other_owner,
        )

        response = self.client.delete(f"/api/templates/{template.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(MessageTemplate.objects.filter(id=template.id).exists())

    def test_unauthenticated_delete_is_rejected(self):
        template = self.create_template()
        self.client.force_authenticate(user=None)

        response = self.client.delete(f"/api/templates/{template.id}/")

        self.assertEqual(response.status_code, 401)
        self.assertTrue(MessageTemplate.objects.filter(id=template.id).exists())

    def test_delete_used_template_returns_dependency_conflict(self):
        template = self.create_template()
        BroadcastCampaign.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Order campaign",
            template=template,
            template_language=template.language,
        )

        response = self.client.delete(f"/api/templates/{template.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["dependencies"], {"broadcasts": 1})
        self.assertIn("1 broadcast", response.data["detail"])
        self.assertTrue(MessageTemplate.objects.filter(id=template.id).exists())

    def test_delete_detects_json_automation_and_flow_references(self):
        template = self.create_template()
        AutomationRule.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Template automation",
            trigger_type=AutomationRule.TRIGGER_CONTACT_CREATED,
            actions_json=[{"type": "send_template", "template_id": template.id}],
        )
        CustomerFlow.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Template flow",
            steps_json=[{"type": "send_template", "template_id": str(template.id)}],
        )

        response = self.client.delete(f"/api/templates/{template.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["dependencies"], {"automations": 1, "flows": 1})
        self.assertTrue(MessageTemplate.objects.filter(id=template.id).exists())

    def test_create_and_edit_trim_fields_and_preserve_organization(self):
        create_response = self.client.post(
            "/api/templates/",
            {
                "name": "  delivery_notice  ",
                "language": " EN_US ",
                "category": "utility",
                "status": "draft",
                "header_type": "none",
                "body_text": "  Your delivery is ready.  ",
                "buttons_json": [],
            },
            format="json",
        )
        template_id = create_response.data["id"]
        update_response = self.client.patch(
            f"/api/templates/{template_id}/",
            {"body_text": "  Updated delivery text.  ", "status": "pending"},
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(update_response.status_code, 200)
        template = MessageTemplate.objects.get(id=template_id)
        self.assertEqual(template.organization, self.organization)
        self.assertEqual(template.name, "delivery_notice")
        self.assertEqual(template.language, "en_us")
        self.assertEqual(template.body_text, "Updated delivery text.")
        self.assertEqual(template.status, MessageTemplate.STATUS_PENDING)

    def test_invalid_status_and_duplicate_create_return_clear_errors(self):
        self.create_template(name="duplicate", language="en_us")

        invalid_status = self.client.post(
            "/api/templates/",
            {"name": "new", "language": "en_us", "body_text": "Body", "status": "unknown"},
            format="json",
        )
        duplicate = self.client.post(
            "/api/templates/",
            {"name": "duplicate", "language": "en_us", "body_text": "Body"},
            format="json",
        )

        self.assertEqual(invalid_status.status_code, 400)
        self.assertIn("status", invalid_status.data)
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("name", duplicate.data)

    @patch("templates.views.broadcast_inbox_event")
    @patch("templates.views.send_whatsapp_template_message")
    def test_approved_template_send_validates_parameters_and_creates_one_message(self, send_mock, _broadcast_mock):
        template = self.create_template()
        contact = Contact.objects.create(organization=self.organization, phone_number="15551230001")
        send_mock.return_value = SimpleNamespace(external_message_id="wamid.template")

        missing_parameters = self.client.post(
            f"/api/templates/{template.id}/send/",
            {"contact_id": contact.id, "parameters": []},
            format="json",
        )
        success = self.client.post(
            f"/api/templates/{template.id}/send/",
            {"contact_id": contact.id, "parameters": ["Customer"]},
            format="json",
        )

        self.assertEqual(missing_parameters.status_code, 400)
        self.assertIn("parameters", missing_parameters.data)
        self.assertEqual(success.status_code, 201)
        self.assertEqual(Message.objects.count(), 1)

    @patch("templates.views.broadcast_inbox_event")
    @patch("templates.views.send_whatsapp_template_message", side_effect=WhatsAppSendError("Safe Meta error."))
    def test_send_failure_records_one_failed_message(self, _send_mock, _broadcast_mock):
        template = self.create_template(body_text="Hello")
        contact = Contact.objects.create(organization=self.organization, phone_number="15551230002")

        response = self.client.post(
            f"/api/templates/{template.id}/send/",
            {"contact_id": contact.id, "parameters": []},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Safe Meta error.")
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Message.objects.get().delivery_status, Message.DELIVERY_FAILED)
