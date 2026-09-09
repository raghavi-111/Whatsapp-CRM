from unittest.mock import patch

from rest_framework.test import APITestCase

from accounts.models import User
from contacts.models import Contact
from organizations.models import OrganizationMember, create_organization_for_user
from pipelines.models import Deal

from .models import Lead, Service
from .serializers import LeadSerializer


class LeadApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user("lead-owner@example.com", "pass1234")
        self.organization = create_organization_for_user(self.owner, "Lead Org")
        self.other = User.objects.create_user("other-owner@example.com", "pass1234")
        self.other_org = create_organization_for_user(self.other, "Other Org")
        self.agent = User.objects.create_user("agent@example.com", "pass1234")
        OrganizationMember.objects.create(organization=self.organization, user=self.agent, role="agent", status="active")
        self.other_agent = User.objects.create_user("other-agent@example.com", "pass1234")
        OrganizationMember.objects.create(organization=self.other_org, user=self.other_agent, role="agent", status="active")
        self.service = Service.objects.create(organization=self.organization, name="Consulting", code="consulting")
        self.other_service = Service.objects.create(organization=self.other_org, name="Hosting", code="hosting")
        self.client.force_authenticate(self.owner)

    def payload(self, **changes):
        data = {"name": "Alice Prospect", "phone": "+1 555 201 1000", "email": "alice@example.com", "service": self.service.id, "source": "website", "status": "new", "assigned_to": self.agent.id}
        data.update(changes)
        return data

    def test_valid_lead_creation_and_phone_normalization(self):
        response = self.client.post("/api/leads/", self.payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["phone"], "15552011000")
        self.assertEqual(Lead.objects.get().organization, self.organization)

    def test_service_and_assignee_from_other_organization_are_rejected(self):
        service_response = self.client.post("/api/leads/", self.payload(service=self.other_service.id), format="json")
        assignee_response = self.client.post("/api/leads/", self.payload(assigned_to=self.other_agent.id), format="json")
        self.assertEqual(service_response.status_code, 400)
        self.assertEqual(assignee_response.status_code, 400)

    def test_organization_isolation_for_leads_and_services(self):
        foreign = Lead.objects.create(organization=self.other_org, name="Hidden", phone="123", service=self.other_service)
        list_response = self.client.get("/api/leads/")
        detail_response = self.client.get(f"/api/leads/{foreign.id}/")
        services_response = self.client.get("/api/leads/services/")
        self.assertEqual(list_response.data["count"], 0)
        self.assertEqual(detail_response.status_code, 404)
        self.assertNotIn(self.other_service.id, [item["id"] for item in services_response.data])

    def test_search_and_filters(self):
        wanted = Lead.objects.create(organization=self.organization, name="Needle Customer", phone="111", email="needle@example.com", service=self.service, source="referral", status="interested", assigned_to=self.agent)
        Lead.objects.create(organization=self.organization, name="Other", phone="222", service=self.service, source="website", status="new")
        response = self.client.get("/api/leads/", {"search": "needle", "service": self.service.id, "source": "referral", "status": "interested", "assigned_to": self.agent.id})
        self.assertEqual([item["id"] for item in response.data["results"]], [wanted.id])

    def test_conversion_and_duplicate_prevention(self):
        contact = Contact.objects.create(organization=self.organization, full_name="Alice", phone_number="15552011000")
        lead = Lead.objects.create(organization=self.organization, contact=contact, name="Alice deal", phone="15552011000", service=self.service, status="interested", assigned_to=self.agent, notes="Lead note")
        response = self.client.post(f"/api/leads/{lead.id}/convert/")
        self.assertEqual(response.status_code, 201)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "converted")
        self.assertEqual(lead.converted_deal.contact, contact)
        self.assertEqual(lead.converted_deal.stage, Deal.STAGE_NEW)
        duplicate = self.client.post(f"/api/leads/{lead.id}/convert/")
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(Deal.objects.count(), 1)

    def test_collector_lead_conversion_creates_contact_and_reuses_normalized_existing_contact(self):
        existing = Contact.objects.create(
            organization=self.organization,
            full_name="Existing customer",
            phone_number="+1 (555) 201-1000",
        )
        lead = Lead.objects.create(
            organization=self.organization,
            name="Collected business",
            phone="15552011000",
            email="collected@example.com",
            service=self.service,
            source=Lead.SOURCE_LEAD_COLLECTOR,
            status=Lead.STATUS_INTERESTED,
        )
        response = self.client.post(f"/api/leads/{lead.id}/convert/")
        self.assertEqual(response.status_code, 201)
        lead.refresh_from_db()
        self.assertEqual(lead.contact, existing)
        self.assertEqual(lead.converted_deal.contact, existing)
        self.assertEqual(Contact.objects.filter(organization=self.organization).count(), 1)
        self.assertEqual(self.client.post(f"/api/leads/{lead.id}/convert/").status_code, 400)

    def test_conversion_fails_without_initial_stage(self):
        lead = Lead.objects.create(organization=self.organization, name="Ready", phone="123", service=self.service, status="interested")
        with patch.object(Deal, "STAGE_CHOICES", [("Qualified", "Qualified")]):
            response = self.client.post(f"/api/leads/{lead.id}/convert/")
        self.assertEqual(response.status_code, 400)
        lead.refresh_from_db()
        self.assertIsNone(lead.converted_deal)
        self.assertEqual(lead.status, "interested")

    def test_agents_cannot_manage_services_or_delete_leads(self):
        lead = Lead.objects.create(organization=self.organization, name="Protected", phone="123", service=self.service)
        self.client.force_authenticate(self.agent)
        self.assertEqual(self.client.post("/api/leads/services/", {"name": "No", "code": "NO"}).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/leads/{lead.id}/").status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/leads/").status_code, 401)

    def test_serializer_blocks_cross_org_contact_and_direct_conversion(self):
        contact = Contact.objects.create(organization=self.other_org, full_name="Foreign", phone_number="999")
        contact_serializer = LeadSerializer(data=self.payload(contact=contact.id), context={"organization": self.organization})
        status_serializer = LeadSerializer(data=self.payload(status="converted"), context={"organization": self.organization})
        self.assertFalse(contact_serializer.is_valid())
        self.assertIn("contact", contact_serializer.errors)
        self.assertFalse(status_serializer.is_valid())
        self.assertIn("status", status_serializer.errors)
