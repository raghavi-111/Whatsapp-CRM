import logging

from .base import EnrichmentError
from .hotel_website import enrich_hotel_from_website


logger = logging.getLogger(__name__)
CONTACT_FIELDS = ('address', 'phone', 'email', 'website', 'brand')
MAX_BULK_HOTELS = 10


def _existing_sources(hotel):
    label = hotel.get('source') or 'OpenStreetMap'
    return {field: label if hotel.get(field) else None for field in CONTACT_FIELDS}


def enrich_hotels_bulk(hotels):
    results = []
    field_additions = {field: 0 for field in CONTACT_FIELDS}
    for hotel in hotels:
        merged = {field: hotel.get(field) for field in CONTACT_FIELDS}
        sources = _existing_sources(hotel)
        fields_added = []
        social_profiles = {'linkedin': None, 'facebook': None, 'instagram': None}
        social_profile_sources = {'linkedin': None, 'facebook': None, 'instagram': None}
        discovered_pages = {
            'contact': None, 'about': None, 'team': None, 'leadership': None,
            'management': None, 'sales': None, 'press': None,
        }
        business_emails = []
        business_phones = []
        whatsapp_contacts = []
        decision_makers = []
        try:
            enriched = enrich_hotel_from_website(hotel)
            for field in CONTACT_FIELDS:
                if not merged.get(field) and enriched.get(field):
                    merged[field] = enriched[field]
                    sources[field] = enriched.get('sources', {}).get(field)
                    fields_added.append(field)
                    field_additions[field] += 1
            status = 'FOUND' if len(fields_added) > 1 else (
                'PARTIAL' if fields_added else 'NOT_FOUND'
            )
            confidence = enriched.get('website_confidence')
            social_profiles.update(enriched.get('social_profiles') or {})
            social_profile_sources.update(enriched.get('social_profile_sources') or {})
            discovered_pages.update(enriched.get('discovered_pages') or {})
            business_emails = enriched.get('business_emails') or []
            business_phones = enriched.get('business_phones') or []
            whatsapp_contacts = enriched.get('whatsapp_contacts') or []
            decision_makers = enriched.get('decision_makers') or []
        except EnrichmentError:
            logger.exception('Free website enrichment failed for %s.', hotel['name'])
            status = 'ERROR'
            confidence = None
        except Exception:
            # Third-party pages are untrusted input. A malformed page must not
            # abort preparation of every otherwise valid export row.
            logger.exception('Unexpected website enrichment failure for %s.', hotel['name'])
            status = 'ERROR'
            confidence = None
        results.append({
            'hotel_name': hotel['name'],
            'status': status,
            'hotel': merged,
            'sources': sources,
            'fields_added': fields_added,
            'website_confidence': confidence,
            'social_profiles': social_profiles,
            'social_profile_sources': social_profile_sources,
            'discovered_pages': discovered_pages,
            'business_emails': business_emails,
            'business_phones': business_phones,
            'whatsapp_contacts': whatsapp_contacts,
            'decision_makers': decision_makers,
        })

    return {
        'results': results,
        'summary': {
            'requested': len(hotels),
            'processed': len(results),
            'improved': sum(bool(result['fields_added']) for result in results),
            'not_improved': sum(result['status'] == 'NOT_FOUND' for result in results),
            'errors': sum(result['status'] == 'ERROR' for result in results),
            'fields_added': field_additions,
        },
    }
