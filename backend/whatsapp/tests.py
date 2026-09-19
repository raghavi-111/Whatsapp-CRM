from unittest.mock import patch
from io import BytesIO
import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from automations.models import AutomationLog, AutomationRule
from automations.services import run_automations
from contacts.models import Contact
from conversations.models import Conversation, Message
from flows.models import CustomerFlow, FlowRun
from organizations.models import create_organization_for_user
from support.models import Tag
from .dispatching import dispatch_inbound_consumers
from .models import InboundDispatchLog, WhatsAppBusinessConfig
from .sending import WhatsAppSendError, force_whatsapp_send_mode, send_whatsapp_media_message, send_whatsapp_text_message
from .webhook import handle_status_event, valid_webhook_signature


class GraphResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class WhatsAppConnectionTestEndpointTests(TestCase):
    endpoint = "/api/whatsapp/config/test-connection/"

    def setUp(self):
        self.user = get_user_model().objects.create_user(email="connection-test@example.com")
        self.organization = create_organization_for_user(self.user, "Connection Test")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.config = WhatsAppBusinessConfig.objects.create(
            organization=self.organization,
            business_name="Safe Business",
            phone_number_id="phone-id",
            whatsapp_business_account_id="waba-id",
            meta_app_id="app-id",
            meta_app_secret="top-secret-app-secret",
            access_token="top-secret-access-token",
            webhook_verify_token="top-secret-verify-token",
            is_active=True,
        )

    @patch("whatsapp.connection.urlopen", return_value=GraphResponse({
        "id": "phone-id", "display_phone_number": "+1 555 0100", "verified_name": "Safe Business"
    }))
    def test_success_calls_phone_metadata_endpoint_and_exposes_only_safe_data(self, mocked_open):
        response = self.client.post(self.endpoint, {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["verified_name"], "Safe Business")
        serialized = json.dumps(response.data)
        self.assertNotIn("top-secret", serialized)
        request = mocked_open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("/v21.0/phone-id?", request.full_url)
        self.assertEqual(mocked_open.call_args.kwargs["timeout"], 15)

    @patch("whatsapp.connection.urlopen")
    def test_invalid_token_has_safe_error(self, mocked_open):
        body = BytesIO(json.dumps({"error": {"message": "token details", "code": 190}}).encode())
        mocked_open.side_effect = HTTPError("safe-url", 401, "Unauthorized", {}, body)
        response = self.client.post(self.endpoint, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("rejected the access token", response.data["message"])
        self.assertNotIn("token details", json.dumps(response.data))

    @patch("whatsapp.connection.urlopen")
    def test_missing_access_token_does_not_call_meta(self, mocked_open):
        self.config.access_token = ""
        self.config.save(update_fields=["access_token"])
        response = self.client.post(self.endpoint, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Access Token is missing", response.data["message"])
        mocked_open.assert_not_called()

    @patch("whatsapp.connection.urlopen")
    def test_missing_phone_number_id_does_not_call_meta(self, mocked_open):
        self.config.phone_number_id = ""
        self.config.save(update_fields=["phone_number_id"])
        response = self.client.post(self.endpoint, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Phone Number ID is missing", response.data["message"])
        mocked_open.assert_not_called()

    @patch("whatsapp.connection.urlopen")
    def test_inactive_configuration_does_not_call_meta(self, mocked_open):
        self.config.is_active = False
        self.config.save(update_fields=["is_active"])
        response = self.client.post(self.endpoint, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("inactive", response.data["message"])
        mocked_open.assert_not_called()

    @patch("whatsapp.connection.urlopen", side_effect=URLError("network down"))
    def test_network_failure_is_reported_safely(self, _mocked_open):
        response = self.client.post(self.endpoint, {}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertIn("unavailable or timed out", response.data["message"])
        self.assertNotIn("network down", json.dumps(response.data))

    @patch("whatsapp.views.test_whatsapp_connection", return_value={"phone_number_id": "phone-id"})
    def test_organization_isolation_uses_authenticated_users_config(self, mocked_test):
        other_user = get_user_model().objects.create_user(email="other-connection-test@example.com")
        other_organization = create_organization_for_user(other_user, "Other Connection Test")
        WhatsAppBusinessConfig.objects.create(
            organization=other_organization,
            phone_number_id="other-phone-id",
            whatsapp_business_account_id="other-waba-id",
            meta_app_secret="other-secret",
            access_token="other-token",
            webhook_verify_token="other-verify",
        )
        response = self.client.post(self.endpoint, {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked_test.call_args.args[0].organization_id, self.organization.id)


class ManualWhatsAppSendingTests(TestCase):
    def setUp(self):
        self.config = SimpleNamespace(phone_number_id="phone-id", access_token="secret-token")

    @patch("whatsapp.sending.urlopen", return_value=GraphResponse({"messages": [{"id": "wamid.1"}]}))
    def test_text_send_normalizes_number_and_uses_expected_payload(self, mocked_open):
        with force_whatsapp_send_mode("real"):
            result = send_whatsapp_text_message(self.config, "+1 (555) 123-4567", "Hello")
        request = mocked_open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(result.external_message_id, "wamid.1")
        self.assertEqual(payload, {
            "messaging_product": "whatsapp", "recipient_type": "individual", "to": "15551234567",
            "type": "text", "text": {"preview_url": False, "body": "Hello"},
        })
        self.assertEqual(request.headers["Authorization"], "Bearer secret-token")

    @patch("whatsapp.sending.urlopen")
    def test_meta_authentication_rejection_is_readable(self, mocked_open):
        body = BytesIO(json.dumps({"error": {"message": "Authentication Error", "type": "OAuthException", "code": 190, "fbtrace_id": "trace"}}).encode())
        mocked_open.side_effect = HTTPError("https://graph.facebook.com", 401, "Unauthorized", {}, body)
        with force_whatsapp_send_mode("real"), self.assertRaisesRegex(WhatsAppSendError, "authentication failed"):
            send_whatsapp_text_message(self.config, "15551234567", "Hello")

    def test_missing_configuration_is_rejected(self):
        with force_whatsapp_send_mode("real"), self.assertRaisesRegex(WhatsAppSendError, "Missing active"):
            send_whatsapp_text_message(None, "15551234567", "Hello")

    @patch("whatsapp.sending.urlopen", return_value=GraphResponse({"messages": [{"id": "wamid.media"}]}))
    def test_media_send_uses_meta_media_id_and_normalized_number(self, mocked_open):
        with force_whatsapp_send_mode("real"):
            result = send_whatsapp_media_message(self.config, "+91 98765-43210", "image", meta_media_id="media-id")
        payload = json.loads(mocked_open.call_args.args[0].data)
        self.assertEqual(result.external_message_id, "wamid.media")
        self.assertEqual(payload["to"], "919876543210")
        self.assertEqual(payload["image"], {"id": "media-id"})


class WhatsAppWebhookSecurityAndOrderingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="webhook-order@example.com")
        self.organization = create_organization_for_user(self.user, "Webhook Ordering")
        self.config = WhatsAppBusinessConfig.objects.create(
            organization=self.organization,
            phone_number_id="phone-id",
            whatsapp_business_account_id="waba-id",
            meta_app_secret="app-secret",
            access_token="access-token",
            webhook_verify_token="verify-token",
        )
        self.contact = Contact.objects.create(organization=self.organization, phone_number="15550001234")
        self.conversation = Conversation.objects.create(organization=self.organization, contact=self.contact)

    def test_webhook_signature_uses_raw_body_and_app_secret(self):
        raw_body = b'{"entry":[]}'
        digest = __import__("hmac").new(b"app-secret", raw_body, __import__("hashlib").sha256).hexdigest()
        self.assertTrue(valid_webhook_signature(raw_body, f"sha256={digest}", "app-secret"))
        self.assertFalse(valid_webhook_signature(raw_body, f"sha256={digest}", "wrong-secret"))
        self.assertFalse(valid_webhook_signature(raw_body, "", "app-secret"))

    def test_read_message_does_not_regress_to_delivered_or_failed(self):
        message = Message.objects.create(
            organization=self.organization,
            conversation=self.conversation,
            sender_type=Message.SENDER_AGENT,
            direction=Message.DIRECTION_OUTBOUND,
            external_message_id="wamid-ordered",
            delivery_status=Message.DELIVERY_READ,
        )
        base = {"phone_number_id": "phone-id", "message_id": "wamid-ordered", "timestamp": "1735689600"}
        self.assertEqual(handle_status_event({**base, "status": Message.DELIVERY_DELIVERED}), "stale")
        self.assertEqual(handle_status_event({**base, "status": Message.DELIVERY_FAILED}), "stale")
        message.refresh_from_db()
        self.assertEqual(message.delivery_status, Message.DELIVERY_READ)

    def test_signed_inbound_routes_to_matching_org_and_duplicate_is_idempotent(self):
        other_user = get_user_model().objects.create_user(email="webhook-other@example.com")
        other_org = create_organization_for_user(other_user, "Webhook Other")
        WhatsAppBusinessConfig.objects.create(
            organization=other_org,
            phone_number_id="other-phone-id",
            whatsapp_business_account_id="other-waba-id",
            meta_app_secret="other-app-secret",
            access_token="other-access-token",
            webhook_verify_token="other-verify-token",
        )
        payload = {
            "entry": [{"changes": [{"value": {
                "metadata": {"phone_number_id": "phone-id"},
                "contacts": [{"wa_id": "15550009999", "profile": {"name": "Signed Sender"}}],
                "messages": [{
                    "id": "wamid.signed.once", "from": "15550009999", "timestamp": "1735689600",
                    "type": "text", "text": {"body": "Hello"},
                }],
            }}]}],
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode()
        digest = __import__("hmac").new(b"app-secret", raw_body, __import__("hashlib").sha256).hexdigest()
        client = APIClient()
        first = client.post(
            "/api/whatsapp/webhook/", raw_body, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}",
        )
        second = client.post(
            "/api/whatsapp/webhook/", raw_body, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}",
        )
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(Message.objects.filter(external_message_id="wamid.signed.once").count(), 1)
        self.assertTrue(Contact.objects.filter(organization=self.organization, phone_number="15550009999").exists())
        self.assertFalse(Contact.objects.filter(organization=other_org, phone_number="15550009999").exists())


class ManualInboxFailureTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="manual-send@example.com")
        self.organization = create_organization_for_user(self.user, "Manual Send Test")
        self.contact = Contact.objects.create(organization=self.organization, phone_number="15551234567")
        self.conversation = Conversation.objects.create(organization=self.organization, contact=self.contact)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch("conversations.views.send_whatsapp_text_message", side_effect=WhatsAppSendError("Message failed: Authentication Error"))
    def test_failed_manual_send_creates_exactly_one_failed_record(self, _mocked_send):
        response = self.client.post(
            f"/api/conversations/{self.conversation.id}/messages/",
            {"text": "Hello", "message_type": "text"},
            format="json",
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Message failed: Authentication Error")
        messages = Message.objects.filter(conversation=self.conversation)
        self.assertEqual(messages.count(), 1)
        self.assertEqual(messages.get().delivery_status, Message.DELIVERY_FAILED)


@patch.dict("os.environ", {"WHATSAPP_SEND_MODE": "mock"}, clear=False)
class InboundConsumerIsolationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="dispatch@example.com", password="test-pass-123")
        self.organization = create_organization_for_user(self.user, "Dispatch Test")
        self.client = APIClient(); self.client.force_authenticate(self.user)
        self.contact = Contact.objects.create(organization=self.organization, phone_number="15550001111")
        self.conversation = Conversation.objects.create(organization=self.organization, contact=self.contact)

    def inbound(self, text="hello", external_id="wamid-inbound"):
        return Message.objects.create(organization=self.organization, conversation=self.conversation, sender_type=Message.SENDER_CONTACT, direction=Message.DIRECTION_INBOUND, text=text, external_message_id=external_id, delivery_status=Message.DELIVERY_DELIVERED)

    def automation(self, active=True):
        return AutomationRule.objects.create(organization=self.organization, name="Welcome Automation", trigger_type=AutomationRule.TRIGGER_INBOUND_MESSAGE_RECEIVED, conditions_json=[], actions_json=[{"type": "send_message", "text": "Automation reply"}], is_active=active)

    def flow(self, steps=None):
        return CustomerFlow.objects.create(organization=self.organization, name="Customer Enquiry", status=CustomerFlow.STATUS_ACTIVE, start_trigger_json={"type": "message_contains", "value": "hello"}, steps_json=steps or [{"type": "send_text", "text": "Flow reply"}, {"type": "end"}])

    def synchronous_automation(self, trigger_type, organization, context):
        run_automations(trigger_type, organization, context)

    def test_active_flow_runs_with_no_active_automation(self):
        self.automation(active=False); self.flow(); message = self.inbound()
        result = dispatch_inbound_consumers(self.organization, self.contact, self.conversation, message)
        self.assertEqual(result["automation"], "skipped"); self.assertEqual(result["flow"], "started")
        self.assertTrue(Message.objects.filter(conversation=self.conversation, direction="outbound", text="Flow reply").exists())

    def test_active_automation_runs_with_no_active_flow(self):
        self.automation(); message = self.inbound()
        with patch("whatsapp.dispatching.enqueue_automations", side_effect=self.synchronous_automation):
            result = dispatch_inbound_consumers(self.organization, self.contact, self.conversation, message)
        self.assertEqual(result, {"automation": "dispatched", "flow": "skipped"})
        self.assertTrue(AutomationLog.objects.filter(rule__name="Welcome Automation", status="success").exists())

    def test_matching_automation_and_flow_both_run(self):
        self.automation(); self.flow(); message = self.inbound()
        with patch("whatsapp.dispatching.enqueue_automations", side_effect=self.synchronous_automation): dispatch_inbound_consumers(self.organization, self.contact, self.conversation, message)
        texts = set(Message.objects.filter(conversation=self.conversation, direction="outbound").values_list("text", flat=True))
        self.assertTrue({"Automation reply", "Flow reply"}.issubset(texts))

    def test_automation_dispatch_exception_does_not_block_flow(self):
        self.automation(); self.flow(); message = self.inbound()
        with patch("whatsapp.dispatching.enqueue_automations", side_effect=RuntimeError("automation queue failed")): result = dispatch_inbound_consumers(self.organization, self.contact, self.conversation, message)
        self.assertEqual(result["automation"], "failed"); self.assertEqual(result["flow"], "started")
        self.assertTrue(InboundDispatchLog.objects.filter(message=message, engine="automation", status="failed").exists())

    def test_flow_exception_does_not_block_automation(self):
        self.automation(); self.flow(); message = self.inbound()
        with patch("whatsapp.dispatching.enqueue_automations", side_effect=self.synchronous_automation), patch("whatsapp.dispatching.trigger_flows_for_inbound", side_effect=RuntimeError("flow failed")):
            result = dispatch_inbound_consumers(self.organization, self.contact, self.conversation, message)
        self.assertEqual(result["automation"], "dispatched"); self.assertEqual(result["flow"], "failed")
        self.assertTrue(AutomationLog.objects.filter(status="success").exists())

    def test_waiting_flow_resumes_while_automations_disabled(self):
        self.automation(active=False)
        self.flow([{"type": "send_text", "text": "Choose"}, {"type": "wait_reply"}, {"type": "add_tag", "tag_name": "Replied"}, {"type": "end"}])
        first = self.inbound(); dispatch_inbound_consumers(self.organization, self.contact, self.conversation, first)
        self.assertEqual(FlowRun.objects.get(contact=self.contact).status, FlowRun.STATUS_WAITING)
        reply = self.inbound("1", "wamid-reply"); result = dispatch_inbound_consumers(self.organization, self.contact, self.conversation, reply)
        self.assertEqual(result["automation"], "skipped"); self.assertEqual(result["flow"], "resumed")
        self.assertTrue(Tag.objects.filter(name="Replied", contacts=self.contact).exists())

    def test_duplicate_message_dispatches_neither_engine_twice(self):
        self.automation(); self.flow(); message = self.inbound()
        with patch("whatsapp.dispatching.enqueue_automations", side_effect=self.synchronous_automation):
            dispatch_inbound_consumers(self.organization, self.contact, self.conversation, message)
            outbound_count = Message.objects.filter(conversation=self.conversation, direction="outbound").count()
            result = dispatch_inbound_consumers(self.organization, self.contact, self.conversation, message)
        self.assertEqual(result, {"automation": "skipped", "flow": "skipped"})
        self.assertEqual(Message.objects.filter(conversation=self.conversation, direction="outbound").count(), outbound_count)

    def simulate(self, text="hello", message_id=""):
        payload = {"conversation_id": self.conversation.id, "text": text}
        if message_id: payload["message_id"] = message_id
        return self.client.post("/api/whatsapp/simulate-inbound/", payload, format="json")

    def test_simulator_starts_flow_without_automation(self):
        self.flow(); response = self.simulate()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(FlowRun.objects.filter(contact=self.contact).exists())
        self.assertTrue(InboundDispatchLog.objects.filter(message_id=response.data["message"]["id"], engine="automation", status="skipped").exists())
        self.assertTrue(InboundDispatchLog.objects.filter(message_id=response.data["message"]["id"], engine="flow", status="dispatched").exists())

    def test_simulator_resumes_waiting_flow(self):
        self.flow([{"type": "send_text", "text": "Choose"}, {"type": "wait_reply"}, {"type": "add_tag", "tag_name": "Simulated Reply"}, {"type": "end"}])
        self.simulate("hello", "sim-start"); response = self.simulate("1", "sim-reply")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(FlowRun.objects.get(contact=self.contact).status, FlowRun.STATUS_COMPLETED)
        self.assertTrue(Tag.objects.filter(name="Simulated Reply", contacts=self.contact).exists())

    def test_simulator_dispatches_active_automation_and_flow(self):
        self.automation(); self.flow(); response = self.simulate()
        self.assertEqual(response.status_code, 201)
        texts = set(Message.objects.filter(conversation=self.conversation, direction="outbound").values_list("text", flat=True))
        self.assertTrue({"Automation reply", "Flow reply"}.issubset(texts))

    def test_simulator_automation_failure_does_not_block_flow(self):
        self.automation(); self.flow()
        with patch("whatsapp.dispatching.run_automations", side_effect=RuntimeError("simulated automation failure")): response = self.simulate()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Message.objects.filter(conversation=self.conversation, text="Flow reply").exists())
        self.assertTrue(InboundDispatchLog.objects.filter(message_id=response.data["message"]["id"], engine="automation", status="failed").exists())

    def test_simulator_flow_failure_does_not_block_automation(self):
        self.automation(); self.flow()
        with patch("whatsapp.dispatching.trigger_flows_for_inbound", side_effect=RuntimeError("simulated flow failure")): response = self.simulate()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Message.objects.filter(conversation=self.conversation, text="Automation reply").exists())
        self.assertTrue(InboundDispatchLog.objects.filter(message_id=response.data["message"]["id"], engine="flow", status="failed").exists())

    def test_simulator_duplicate_message_id_executes_neither_twice(self):
        self.automation(); self.flow(); first = self.simulate(message_id="stable-simulation-id")
        outbound_count = Message.objects.filter(conversation=self.conversation, direction="outbound").count()
        second = self.simulate(message_id="stable-simulation-id")
        self.assertEqual(first.status_code, 201); self.assertEqual(second.status_code, 200); self.assertTrue(second.data["duplicate"])
        self.assertEqual(Message.objects.filter(conversation=self.conversation, direction="outbound").count(), outbound_count)

    def test_simulator_always_records_both_engine_dispatch_logs(self):
        response = self.simulate(message_id="logged-simulation")
        self.assertEqual(set(InboundDispatchLog.objects.filter(message_id=response.data["message"]["id"]).values_list("engine", flat=True)), {"automation", "flow"})
