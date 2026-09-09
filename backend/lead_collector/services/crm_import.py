from django.db import transaction

from leads.models import Lead, Service
from organizations.models import Organization

from lead_collector.models import LeadImportRecord
from .identity import confirmed_whatsapp, normalized_domain, normalized_phone, provider_place_id


def duplicate_for(organization, business):
    payload = business.payload
    whatsapp = confirmed_whatsapp(payload)
    phone = normalized_phone(payload.get("phone"))
    domain = normalized_domain(payload.get("website"))
    place_id = provider_place_id(payload)
    records = LeadImportRecord.objects.filter(organization=organization).select_related("lead")
    if whatsapp:
        match = records.filter(whatsapp_normalized=whatsapp).first()
        if match: return match.lead, "confirmed_whatsapp"
    if phone:
        match = records.filter(phone_normalized=phone).first()
        if match: return match.lead, "business_phone"
        match = Lead.objects.filter(organization=organization, phone=phone).first()
        if match: return match, "existing_lead_phone"
    if place_id:
        match = records.filter(provider_place_id=place_id).first()
        if match: return match.lead, "provider_place_id"
    if domain:
        match = records.filter(website_domain=domain).first()
        if match: return match.lead, "website_domain"
    match = records.filter(identity_key=business.identity_key).first()
    return (match.lead, "business_identity") if match else (None, None)


def preview_import(organization, businesses):
    rows = []
    for business in businesses:
        existing, reason = duplicate_for(organization, business)
        phone = normalized_phone(business.payload.get("phone")) or confirmed_whatsapp(business.payload)
        rows.append({
            "business_id": business.id,
            "name": business.name,
            "phone": phone,
            "can_import": bool(phone) and existing is None,
            "existing_lead_id": existing.id if existing else None,
            "duplicate_reason": reason,
            "error": "A usable public phone number is required." if not phone else None,
        })
    return rows


@transaction.atomic
def import_businesses(organization, user, businesses, service_id):
    # Duplicate evidence spans several nullable identifiers (WhatsApp, phone,
    # provider ID, domain, and business identity), so one composite UNIQUE
    # constraint would not express the policy. Serialize collector imports per
    # organization while the evidence check and both creates are atomic.
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    service = Service.objects.filter(organization=organization, id=service_id, is_active=True).first()
    if not service:
        raise ValueError("Select an active service belonging to the current organization.")
    outcomes = []
    for business in businesses:
        existing, reason = duplicate_for(organization, business)
        phone = normalized_phone(business.payload.get("phone")) or confirmed_whatsapp(business.payload)
        if existing:
            outcomes.append({"business_id": business.id, "status": "duplicate", "lead_id": existing.id, "reason": reason})
            continue
        if not phone:
            outcomes.append({"business_id": business.id, "status": "invalid", "reason": "missing_phone"})
            continue
        lead = Lead.objects.create(
            organization=organization, created_by=user, service=service,
            name=business.name, phone=phone, email=business.payload.get("email") or "",
            source=Lead.SOURCE_LEAD_COLLECTOR, status=Lead.STATUS_NEW,
            notes=f"Discovered via Lead Collector. Address: {business.payload.get('address') or 'Not available'}. Website: {business.payload.get('website') or 'Not available'}.",
        )
        LeadImportRecord.objects.create(
            organization=organization, business=business, lead=lead,
            identity_key=business.identity_key,
            phone_normalized=normalized_phone(business.payload.get("phone")),
            whatsapp_normalized=confirmed_whatsapp(business.payload),
            website_domain=normalized_domain(business.payload.get("website")),
            provider_place_id=provider_place_id(business.payload),
        )
        outcomes.append({"business_id": business.id, "status": "created", "lead_id": lead.id})
    return outcomes
