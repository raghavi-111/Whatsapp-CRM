from django.test import TestCase

from accounts.models import User
from automations.models import AutomationLog
from contacts.models import Contact, ContactCategory
from conversations.models import Conversation, Message
from organizations.models import Organization
from pipelines.models import Deal
from pipelines.services import create_lead_deal_for_contact

from lead_collector.models import (
    DiscoveredBusiness,
    DiscoverySearch,
    WhatsAppContactImportRecord,
)
from lead_collector.services.whatsapp_contact_import import (
    INITIAL_CATEGORIES,
    import_whatsapp_contacts,
)


class WhatsAppContactImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="owner@example.com", password="password")
        self.organization = Organization.objects.create(
            name="Primary", slug="primary", owner=self.user
        )
        self.search = DiscoverySearch.objects.create(
            organization=self.organization,
            created_by=self.user,
            location_name="Pune",
            latitude=18.5,
            longitude=73.8,
            radius_m=5000,
            category="hotels_resorts",
            providers=["playwright"],
        )

    def business(self, identity, whatsapp_contacts=None, **payload):
        return DiscoveredBusiness.objects.create(
            organization=self.organization,
            search=self.search,
            identity_key=identity,
            name=payload.pop("name", "Example Hotel"),
            payload={"whatsapp_contacts": whatsapp_contacts or [], **payload},
        )

    def confirmed(self, number="+91 98765 43210", normalized="+919876543210"):
        return {
            "number": number,
            "normalized": normalized,
            "status": "CONFIRMED_PUBLIC",
            "evidence_type": "wa.me",
            "source_url": "https://hotel.example/contact",
        }

    def test_only_confirmed_public_evidence_creates_a_contact_and_provenance(self):
        confirmed = self.business("confirmed", [self.confirmed()], source="Browser Search")
        ordinary = self.business("ordinary", [], phone="+91 90000 00000")
        unknown = self.business("unknown", [{**self.confirmed(), "status": "UNKNOWN"}])

        outcomes = import_whatsapp_contacts(
            self.organization, self.user, [confirmed, ordinary, unknown]
        )

        self.assertEqual([row["status"] for row in outcomes], [
            "created", "skipped_no_confirmed_whatsapp", "skipped_no_confirmed_whatsapp"
        ])
        contact = Contact.objects.get()
        self.assertEqual(contact.phone_number, "+919876543210")
        self.assertEqual(contact.source, Contact.SOURCE_LEAD_COLLECTOR)
        self.assertEqual(contact.category.name, "Hotels & Resorts")
        record = WhatsAppContactImportRecord.objects.get()
        self.assertEqual(record.contact, contact)
        self.assertEqual(record.status, "CONFIRMED_PUBLIC")
        self.assertEqual(record.evidence_type, "wa.me")
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(AutomationLog.objects.count(), 0)

        deal, created = create_lead_deal_for_contact(contact, self.organization, source=Deal.SOURCE_MANUAL)
        repeated, created_again = create_lead_deal_for_contact(contact, self.organization, source=Deal.SOURCE_MANUAL)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(repeated, deal)
        self.assertEqual(deal.contact, contact)
        self.assertEqual(deal.organization, self.organization)
        self.assertEqual(deal.source, Deal.SOURCE_MANUAL)

    def test_normalized_number_is_idempotent_within_an_organization(self):
        business = self.business("duplicate", [
            self.confirmed(),
            self.confirmed(number="91987 654 3210", normalized="919876543210"),
        ])
        first = import_whatsapp_contacts(self.organization, self.user, [business])
        second = import_whatsapp_contacts(self.organization, self.user, [business])
        self.assertEqual(first[0]["status"], "created")
        self.assertEqual(second[0]["status"], "already_exists")
        self.assertEqual(Contact.objects.count(), 1)
        self.assertEqual(WhatsAppContactImportRecord.objects.count(), 1)

    def test_existing_formatted_contact_is_reused_and_only_unknown_category_upgrades(self):
        unknown = ContactCategory.objects.create(organization=self.organization, name="Unknown")
        contact = Contact.objects.create(
            organization=self.organization,
            phone_number="+91 (98765) 43210",
            category=unknown,
        )
        business = self.business("upgrade", [self.confirmed()])
        outcome = import_whatsapp_contacts(self.organization, self.user, [business])[0]
        contact.refresh_from_db()
        self.assertEqual(outcome["status"], "category_updated")
        self.assertEqual(Contact.objects.count(), 1)
        self.assertEqual(contact.category.name, "Hotels & Resorts")
        self.assertEqual(contact.full_name, "Example Hotel")

        self.search.category = "restaurants"
        self.search.save(update_fields=["category"])
        second = self.business("conflict", [self.confirmed()], name="Other Name")
        self.assertEqual(
            import_whatsapp_contacts(self.organization, self.user, [second])[0]["status"],
            "already_exists",
        )
        contact.refresh_from_db()
        self.assertEqual(contact.category.name, "Hotels & Resorts")

    def test_categories_are_initialized_per_organization_and_numbers_are_org_scoped(self):
        business = self.business("org-one", [self.confirmed()])
        import_whatsapp_contacts(self.organization, self.user, [business])
        self.assertEqual(
            set(ContactCategory.objects.filter(organization=self.organization).values_list("name", flat=True)),
            set(INITIAL_CATEGORIES),
        )

        other_user = User.objects.create_user(email="other@example.com", password="password")
        other = Organization.objects.create(name="Other", slug="other", owner=other_user)
        other_search = DiscoverySearch.objects.create(
            organization=other, created_by=other_user, location_name="Pune",
            latitude=18.5, longitude=73.8, radius_m=5000,
            category="unmapped_category", providers=["playwright"],
        )
        other_business = DiscoveredBusiness.objects.create(
            organization=other, search=other_search, identity_key="org-two",
            name="Other Business", payload={"whatsapp_contacts": [self.confirmed()]},
        )
        import_whatsapp_contacts(other, other_user, [other_business])
        self.assertEqual(Contact.objects.count(), 2)
        self.assertEqual(Contact.objects.get(organization=other).category.name, "Unknown")
