from unittest.mock import patch

from rest_framework.test import APITestCase

from accounts.models import User
from contacts.models import Contact
from organizations.models import create_organization_for_user

from .models import Deal


class DealCreationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("pipeline-owner@example.com", "testpass123")
        self.organization = create_organization_for_user(self.user, "Pipeline Org")
        self.client.force_authenticate(user=self.user)

    def post_deal(self, payload):
        with patch("automations.services.enqueue_automations"):
            return self.client.post("/api/pipelines/deals/", payload, format="json")

    def test_existing_contact_workflow_is_unchanged(self):
        contact = Contact.objects.create(
            organization=self.organization,
            full_name="Existing Customer",
            phone_number="15551230001",
        )

        response = self.post_deal(
            {"title": "Existing deal", "value": "25", "stage": "Qualified", "contact": contact.id}
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["contact"], contact.id)
        self.assertEqual(Contact.objects.count(), 1)

    def test_new_lead_creates_and_links_contact(self):
        response = self.post_deal(
            {
                "title": "New opportunity",
                "value": "125.50",
                "stage": "Proposal",
                "notes": "Deal notes",
                "new_lead": {
                    "customer_name": "  New Customer  ",
                    "phone_number": "+1 (555) 123-0002",
                    "email": "customer@example.com",
                    "company": "Example Co",
                    "notes": "Contact notes",
                    "source": "referral",
                },
            }
        )

        self.assertEqual(response.status_code, 201)
        contact = Contact.objects.get()
        deal = Deal.objects.get()
        self.assertEqual(contact.full_name, "New Customer")
        self.assertEqual(contact.phone_number, "15551230002")
        self.assertEqual(contact.email, "customer@example.com")
        self.assertEqual(contact.company_name, "Example Co")
        self.assertEqual(contact.notes, "Contact notes")
        self.assertEqual(contact.source, Contact.SOURCE_REFERRAL)
        self.assertEqual(contact.created_by, self.user)
        self.assertEqual(deal.contact, contact)
        self.assertEqual(deal.stage, Deal.STAGE_PROPOSAL)

    def test_new_lead_reuses_contact_with_same_normalized_phone(self):
        contact = Contact.objects.create(
            organization=self.organization,
            full_name="Original Name",
            phone_number="15551230003",
        )

        response = self.post_deal(
            {
                "title": "Reused customer deal",
                "new_lead": {
                    "customer_name": "Different Name",
                    "phone_number": "+1 555 123 0003",
                },
            }
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Contact.objects.count(), 1)
        self.assertEqual(response.data["contact"], contact.id)
        contact.refresh_from_db()
        self.assertEqual(contact.full_name, "Original Name")

    def test_new_lead_validates_required_and_optional_fields(self):
        missing_name = self.post_deal(
            {"title": "Invalid lead", "new_lead": {"customer_name": "   ", "phone_number": "123"}}
        )
        invalid_phone = self.post_deal(
            {"title": "Invalid lead", "new_lead": {"customer_name": "Customer", "phone_number": "---"}}
        )
        invalid_email = self.post_deal(
            {
                "title": "Invalid lead",
                "new_lead": {"customer_name": "Customer", "phone_number": "123", "email": "invalid"},
            }
        )

        self.assertEqual(missing_name.status_code, 400)
        self.assertEqual(invalid_phone.status_code, 400)
        self.assertEqual(invalid_email.status_code, 400)
        self.assertEqual(Contact.objects.count(), 0)
        self.assertEqual(Deal.objects.count(), 0)
