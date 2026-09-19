from django.db import transaction

from contacts.models import Contact, ContactCategory
from organizations.models import Organization

from lead_collector.models import WhatsAppContactImportRecord
from .identity import normalized_phone


INITIAL_CATEGORIES = (
    "Unknown", "Hotels & Resorts", "Restaurants", "Schools & Education",
    "Hospitals & Clinics", "Real Estate", "Retail Stores", "Salons & Spas",
    "Gyms & Fitness", "Travel & Tourism", "Automotive", "IT / Software",
    "Professional Services", "Construction", "Manufacturing",
    "Finance & Insurance", "Other",
)
CATEGORY_MAP = {
    "hotels_resorts": "Hotels & Resorts", "restaurants": "Restaurants",
    "schools": "Schools & Education", "universities_colleges": "Schools & Education",
    "hospitals": "Hospitals & Clinics", "retail": "Retail Stores",
    "shopping_malls": "Retail Stores", "salons_spas": "Salons & Spas",
    "gyms_fitness": "Gyms & Fitness", "airports": "Travel & Tourism",
    "hostels": "Travel & Tourism", "banks": "Finance & Insurance",
}


def ensure_contact_categories(organization):
    existing = set(ContactCategory.objects.filter(organization=organization).values_list("name", flat=True))
    ContactCategory.objects.bulk_create([
        ContactCategory(organization=organization, name=name)
        for name in INITIAL_CATEGORIES if name not in existing
    ], ignore_conflicts=True)
    return ContactCategory.objects.filter(organization=organization)


def category_for(organization, category_key):
    ensure_contact_categories(organization)
    name = CATEGORY_MAP.get(category_key, "Unknown")
    return ContactCategory.objects.get(organization=organization, name=name)


def confirmed_contacts(payload):
    contacts, seen = [], set()
    for evidence in payload.get("whatsapp_contacts") or []:
        if not isinstance(evidence, dict) or evidence.get("status") != "CONFIRMED_PUBLIC":
            continue
        number = normalized_phone(evidence.get("normalized") or evidence.get("number"))
        if not number or number in seen:
            continue
        seen.add(number); contacts.append((number, evidence))
    return contacts


def preview_whatsapp_contacts(organization, businesses):
    rows = []
    for business in businesses:
        evidence = confirmed_contacts(business.payload)
        if not evidence:
            rows.append({"business_id": business.id, "name": business.name, "status": "skipped_no_confirmed_whatsapp"})
            continue
        category = category_for(organization, business.search.category)
        for number, item in evidence:
            existing = next((contact for contact in Contact.objects.filter(organization=organization) if normalized_phone(contact.phone_number) == number), None)
            rows.append({"business_id": business.id, "name": business.name, "number": number, "category": category.name, "whatsapp_status": "CONFIRMED_PUBLIC", "status": "already_exists" if existing else "ready", "contact_id": existing.id if existing else None, "evidence_url": item.get("source_url")})
    return rows


@transaction.atomic
def import_whatsapp_contacts(organization, user, businesses):
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    outcomes = []
    for business in businesses:
        evidence_rows = confirmed_contacts(business.payload)
        if not evidence_rows:
            outcomes.append({"business_id": business.id, "status": "skipped_no_confirmed_whatsapp"})
            continue
        incoming_category = category_for(organization, business.search.category)
        for number, evidence in evidence_rows:
            contact = next((item for item in Contact.objects.select_for_update().filter(organization=organization) if normalized_phone(item.phone_number) == number), None)
            created = contact is None
            category_updated = False
            if created:
                contact = Contact.objects.create(
                    organization=organization, created_by=user, full_name=business.name,
                    company_name=business.name, phone_number=number,
                    email=business.payload.get("email") or "", category=incoming_category,
                    source=Contact.SOURCE_LEAD_COLLECTOR, status=Contact.STATUS_NEW,
                    notes=f"Confirmed public WhatsApp evidence: {evidence.get('source_url') or 'public business website'}",
                )
            else:
                fields = []
                if not contact.full_name and business.name:
                    contact.full_name = business.name; fields.append("full_name")
                if not contact.company_name and business.name:
                    contact.company_name = business.name; fields.append("company_name")
                if not contact.email and business.payload.get("email"):
                    contact.email = business.payload["email"]; fields.append("email")
                if contact.category is None or contact.category.name == "Unknown":
                    if incoming_category.name != "Unknown":
                        contact.category = incoming_category; fields.append("category"); category_updated = True
                    elif contact.category is None:
                        contact.category = incoming_category; fields.append("category")
                if fields: contact.save(update_fields=fields + ["updated_at"])
            WhatsAppContactImportRecord.objects.get_or_create(
                organization=organization, business=business, normalized_number=number,
                defaults={"contact": contact, "evidence_type": evidence.get("evidence_type") or "", "evidence_url": evidence.get("source_url") or "", "status": "CONFIRMED_PUBLIC", "provider_source": business.payload.get("source") or ""},
            )
            outcomes.append({"business_id": business.id, "contact_id": contact.id, "number": number, "category": contact.category.name if contact.category else "Unknown", "status": "created" if created else "category_updated" if category_updated else "already_exists"})
    return outcomes
