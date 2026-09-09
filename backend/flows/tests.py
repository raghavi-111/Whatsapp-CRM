from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from automations.models import AutomationRule
from contacts.models import Contact
from conversations.models import Conversation, Message
from organizations.models import create_organization_for_user
from support.models import Tag
from .models import CustomerFlow, FlowLog, FlowRun
from .services import trigger_flows_for_inbound


class CustomerFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="flow@example.com", password="test-pass-123")
        self.organization = create_organization_for_user(self.user, "Flow Test")
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def test_flow_api_saves_organization_owned_draft(self):
        response = self.client.post("/api/flows/", {"name": "Welcome", "status": "draft", "start_trigger_json": {"type": "message_contains", "value": "hi"}, "steps_json": [{"type": "send_text", "text": "Hello"}, {"type": "end"}]}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(CustomerFlow.objects.filter(id=response.data["id"], organization=self.organization).exists())

    @patch.dict("os.environ", {"WHATSAPP_SEND_MODE": "mock"}, clear=False)
    def test_flow_waits_for_reply_then_resumes_once(self):
        contact = Contact.objects.create(organization=self.organization, phone_number="15551230001")
        conversation = Conversation.objects.create(organization=self.organization, contact=contact)
        flow = CustomerFlow.objects.create(organization=self.organization, name="Greeting", status="active", start_trigger_json={"type": "message_contains", "value": "hi"}, steps_json=[{"type": "send_text", "text": "Choose 1"}, {"type": "wait_reply"}, {"type": "add_tag", "tag_name": "Price Enquiry"}, {"type": "send_text", "text": "Pricing selected"}, {"type": "end"}])
        first = Message.objects.create(organization=self.organization, conversation=conversation, sender_type="contact", direction="inbound", text="Hi")
        trigger_flows_for_inbound(self.organization, contact, conversation, first)
        run = FlowRun.objects.get(flow=flow, contact=contact); self.assertEqual(run.status, "waiting")
        reply = Message.objects.create(organization=self.organization, conversation=conversation, sender_type="contact", direction="inbound", text="1")
        trigger_flows_for_inbound(self.organization, contact, conversation, reply)
        run.refresh_from_db(); self.assertEqual(run.status, "completed")
        self.assertTrue(Tag.objects.filter(organization=self.organization, contacts=contact, name="Price Enquiry").exists())
        log_count = FlowLog.objects.filter(run=run).count()
        trigger_flows_for_inbound(self.organization, contact, conversation, reply)
        self.assertEqual(FlowLog.objects.filter(run=run).count(), log_count)


@patch.dict("os.environ", {"WHATSAPP_SEND_MODE": "mock"}, clear=False)
class FlowBranchResumeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="branch@example.com", password="test-pass-123")
        self.organization = create_organization_for_user(self.user, "Branch Flow Test")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.contact = Contact.objects.create(organization=self.organization, phone_number="15551230002")
        self.conversation = Conversation.objects.create(organization=self.organization, contact=self.contact)
        self.steps = [
            {"type": "send_text", "text": "Choose: 1 Pricing, 2 Demo, 3 Support"},
            {"type": "wait_reply"},
            {
                "type": "branch",
                "branches": [
                    {"value": "1", "next_step": 4},
                    {"value": 2, "next_step": 6},
                    {"value": "3", "next_step": 8},
                ],
                "unmatched_reply": "Please reply with 1, 2, or 3.",
            },
            {"type": "send_text", "text": "Pricing response"},
            {"type": "end"},
            {"type": "send_text", "text": "Product Demo response"},
            {"type": "end"},
            {"type": "send_text", "text": "Support response"},
            {"type": "end"},
        ]
        self.flow = CustomerFlow.objects.create(
            organization=self.organization,
            name="Menu",
            status=CustomerFlow.STATUS_ACTIVE,
            start_trigger_json={"type": "message_equals", "value": "menu"},
            steps_json=self.steps,
        )

    def inbound(self, text, external_id):
        return Message.objects.create(
            organization=self.organization,
            conversation=self.conversation,
            sender_type=Message.SENDER_CONTACT,
            direction=Message.DIRECTION_INBOUND,
            text=text,
            external_message_id=external_id,
        )

    def start(self):
        trigger_flows_for_inbound(self.organization, self.contact, self.conversation, self.inbound("menu", "branch-start"))
        run = FlowRun.objects.get(flow=self.flow, contact=self.contact)
        self.assertEqual((run.current_step, run.status), (1, FlowRun.STATUS_WAITING))
        return run

    def reply(self, value, external_id="branch-reply"):
        message = self.inbound(value, external_id)
        result = trigger_flows_for_inbound(self.organization, self.contact, self.conversation, message)
        return message, result

    def assert_route(self, reply, expected_text, expected_target):
        run = self.start()
        self.reply(reply)
        run.refresh_from_db()
        self.assertEqual(run.current_step, expected_target)
        self.assertEqual(run.status, FlowRun.STATUS_COMPLETED)
        self.assertTrue(Message.objects.filter(conversation=self.conversation, direction=Message.DIRECTION_OUTBOUND, text=expected_text).exists())

    def test_start_flow_reaches_wait_step(self):
        self.start()

    def test_reply_one_executes_pricing_and_completes(self):
        self.assert_route("1", "Pricing response", 4)

    def test_reply_two_executes_demo_and_completes(self):
        self.assert_route("2", "Product Demo response", 6)

    def test_reply_three_executes_support_and_completes(self):
        self.assert_route("3", "Support response", 8)

    def test_whitespace_reply_is_normalized(self):
        self.assert_route(" 2 ", "Product Demo response", 6)

    def test_unmatched_reply_sends_validation_and_remains_on_branch(self):
        run = self.start()
        self.reply("invalid")
        run.refresh_from_db()
        self.assertEqual((run.current_step, run.status), (2, FlowRun.STATUS_WAITING))
        self.assertTrue(Message.objects.filter(conversation=self.conversation, direction=Message.DIRECTION_OUTBOUND, text="Please reply with 1, 2, or 3.").exists())

    def test_duplicate_inbound_message_does_not_advance_twice(self):
        run = self.start()
        message, _ = self.reply("invalid")
        log_count = FlowLog.objects.filter(run=run).count()
        result = trigger_flows_for_inbound(self.organization, self.contact, self.conversation, message)
        run.refresh_from_db()
        self.assertEqual(result, {"status": "skipped", "reason": "duplicate_message"})
        self.assertEqual((run.current_step, run.status), (2, FlowRun.STATUS_WAITING))
        self.assertEqual(FlowLog.objects.filter(run=run).count(), log_count)

    def test_branch_targets_are_one_based_and_validated(self):
        response = self.client.patch(
            f"/api/flows/{self.flow.id}/",
            {"steps_json": [
                {"type": "wait_reply"},
                {"type": "branch", "branches": [{"value": "1", "next_step": 3}]},
            ]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("between 1 and 2", str(response.data["steps_json"][0]))

    def test_active_run_uses_step_snapshot_after_flow_edit(self):
        run = self.start()
        self.flow.steps_json = [{"type": "send_text", "text": "Edited"}, {"type": "end"}]
        self.flow.save(update_fields=["steps_json", "updated_at"])
        self.reply("2")
        run.refresh_from_db()
        self.assertEqual(run.status, FlowRun.STATUS_COMPLETED)
        self.assertTrue(Message.objects.filter(conversation=self.conversation, text="Product Demo response").exists())
        self.assertFalse(Message.objects.filter(conversation=self.conversation, text="Edited").exists())

    def test_flow_resume_does_not_require_active_automation(self):
        self.assertFalse(AutomationRule.objects.filter(organization=self.organization, is_active=True).exists())
        self.assert_route("3", "Support response", 8)


@patch.dict("os.environ", {"WHATSAPP_SEND_MODE": "mock"}, clear=False)
class FlowRestartLifecycleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="restart@example.com", password="test-pass-123")
        self.organization = create_organization_for_user(self.user, "Restart Flow Test")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.contact = Contact.objects.create(organization=self.organization, phone_number="15551230003", full_name="Waiting Customer")
        self.conversation = Conversation.objects.create(organization=self.organization, contact=self.contact)
        self.steps = [
            {"type": "send_text", "text": "Main menu"},
            {"type": "wait_reply"},
            {"type": "branch", "branches": [{"value": "2", "next_step": 4}], "unmatched_reply": "Choose 2"},
            {"type": "send_text", "text": "Demo branch"},
            {"type": "end"},
        ]
        self.flow = CustomerFlow.objects.create(
            organization=self.organization,
            name="Restartable Menu",
            status=CustomerFlow.STATUS_ACTIVE,
            start_trigger_json={"type": "message_equals", "value": "hi"},
            steps_json=self.steps,
        )

    def inbound(self, text, external_id):
        return Message.objects.create(
            organization=self.organization,
            conversation=self.conversation,
            sender_type=Message.SENDER_CONTACT,
            direction=Message.DIRECTION_INBOUND,
            text=text,
            external_message_id=external_id,
        )

    def dispatch(self, text, external_id):
        message = self.inbound(text, external_id)
        return message, trigger_flows_for_inbound(self.organization, self.contact, self.conversation, message)

    def waiting_run(self):
        self.dispatch("hi", "restart-start")
        return FlowRun.objects.get(flow=self.flow, contact=self.contact, status=FlowRun.STATUS_WAITING)

    def test_fresh_contact_start_trigger_creates_run(self):
        _, result = self.dispatch("hi", "fresh-hi")
        self.assertEqual(result["status"], "started")
        self.assertEqual(FlowRun.objects.get(id=result["run_ids"][0]).status, FlowRun.STATUS_WAITING)

    def test_valid_reply_resumes_latest_waiting_run_and_completes(self):
        run = self.waiting_run()
        _, result = self.dispatch("2", "valid-two")
        run.refresh_from_db()
        self.assertEqual(result, {"status": "resumed", "run_ids": [run.id]})
        self.assertEqual(run.status, FlowRun.STATUS_COMPLETED)
        self.assertTrue(Message.objects.filter(conversation=self.conversation, text="Demo branch").exists())

    def test_matching_start_trigger_cancels_waiting_run_and_restarts(self):
        old_run = self.waiting_run()
        _, result = self.dispatch(" HI ", "restart-hi")
        old_run.refresh_from_db()
        new_run = FlowRun.objects.get(id=result["run_ids"][0])
        self.assertEqual(result["status"], "restarted")
        self.assertEqual(old_run.status, FlowRun.STATUS_CANCELLED)
        self.assertEqual(new_run.status, FlowRun.STATUS_WAITING)
        self.assertNotEqual(old_run.id, new_run.id)
        self.assertEqual(Message.objects.filter(conversation=self.conversation, text="Main menu").count(), 2)
        self.assertTrue(FlowLog.objects.filter(run=old_run, status="cancelled", message__icontains="start trigger").exists())

    def test_completed_contact_can_start_again(self):
        run = self.waiting_run()
        self.dispatch("2", "complete-two")
        run.refresh_from_db()
        self.assertEqual(run.status, FlowRun.STATUS_COMPLETED)
        _, result = self.dispatch("hi", "start-again")
        self.assertEqual(result["status"], "started")
        self.assertTrue(FlowRun.objects.filter(id=result["run_ids"][0], status=FlowRun.STATUS_WAITING).exists())

    def test_invalid_reply_keeps_same_waiting_run(self):
        run = self.waiting_run()
        _, result = self.dispatch("abc", "invalid-abc")
        run.refresh_from_db()
        self.assertEqual(result, {"status": "resumed", "run_ids": [run.id]})
        self.assertEqual(run.status, FlowRun.STATUS_WAITING)
        self.assertEqual(FlowRun.objects.filter(flow=self.flow, contact=self.contact).count(), 1)
        self.assertTrue(Message.objects.filter(conversation=self.conversation, text="Choose 2").exists())

    def test_terminal_runs_are_not_resumed(self):
        for index, terminal_status in enumerate([FlowRun.STATUS_COMPLETED, FlowRun.STATUS_FAILED, FlowRun.STATUS_CANCELLED], 1):
            other_contact = Contact.objects.create(organization=self.organization, phone_number=f"155512301{index:02d}")
            other_conversation = Conversation.objects.create(organization=self.organization, contact=other_contact)
            old = FlowRun.objects.create(organization=self.organization, flow=self.flow, contact=other_contact, conversation=other_conversation, status=terminal_status)
            message = Message.objects.create(organization=self.organization, conversation=other_conversation, sender_type=Message.SENDER_CONTACT, direction=Message.DIRECTION_INBOUND, text="hi", external_message_id=f"terminal-{index}")
            result = trigger_flows_for_inbound(self.organization, other_contact, other_conversation, message)
            self.assertEqual(result["status"], "started")
            old.refresh_from_db()
            self.assertEqual(old.status, terminal_status)

    def test_duplicate_inbound_does_not_restart_twice(self):
        old_run = self.waiting_run()
        message, first = self.dispatch("hi", "one-restart-message")
        second = trigger_flows_for_inbound(self.organization, self.contact, self.conversation, message)
        self.assertEqual(first["status"], "restarted")
        self.assertEqual(second, {"status": "skipped", "reason": "duplicate_message"})
        self.assertEqual(FlowRun.objects.filter(flow=self.flow, contact=self.contact).count(), 2)
        self.assertEqual(FlowRun.objects.filter(flow=self.flow, contact=self.contact, status=FlowRun.STATUS_WAITING).count(), 1)
        self.assertTrue(FlowRun.objects.filter(id=old_run.id, status=FlowRun.STATUS_CANCELLED).exists())

    def test_run_management_is_organization_scoped(self):
        run = self.waiting_run()
        other_user = get_user_model().objects.create_user(email="other-org@example.com", password="test-pass-123")
        create_organization_for_user(other_user, "Other Org")
        other_client = APIClient()
        other_client.force_authenticate(other_user)
        self.assertEqual(other_client.post(f"/api/flows/runs/{run.id}/cancel/").status_code, 404)
        self.assertEqual(other_client.post(f"/api/flows/runs/{run.id}/restart/").status_code, 404)
        run.refresh_from_db()
        self.assertEqual(run.status, FlowRun.STATUS_WAITING)

    def test_legacy_waiting_run_can_be_cancelled_and_restarted(self):
        legacy = FlowRun.objects.create(
            organization=self.organization,
            flow=self.flow,
            contact=self.contact,
            conversation=self.conversation,
            status=FlowRun.STATUS_WAITING,
            current_step=1,
            state_json={},
        )
        listing = self.client.get("/api/flows/runs/")
        serialized = next(item for item in listing.data if item["id"] == legacy.id)
        self.assertTrue(serialized["is_legacy"])
        response = self.client.post(f"/api/flows/runs/{legacy.id}/restart/")
        self.assertEqual(response.status_code, 201)
        legacy.refresh_from_db()
        self.assertEqual(legacy.status, FlowRun.STATUS_CANCELLED)
        self.assertFalse(response.data["run"]["is_legacy"])
        self.assertEqual(response.data["run"]["status"], FlowRun.STATUS_WAITING)
