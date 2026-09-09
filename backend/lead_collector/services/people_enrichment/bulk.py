import logging

from .apollo import search_decision_makers
from .base import PeopleEnrichmentError
from .orchestrator import search_decision_makers_multi_provider


logger = logging.getLogger(__name__)
MAX_BULK_HOTELS = 10
MAX_CONTACTS_PER_HOTEL = 3


def _normalize_contacts(contacts):
    normalized = []
    seen_departments = set()
    for contact in contacts or []:
        if not isinstance(contact, dict):
            continue
        department = contact.get('role_group') or contact.get('department')
        if not department or department in seen_departments:
            continue
        seen_departments.add(department)
        normalized.append({
            'name': contact.get('name'),
            'title': contact.get('title'),
            'department': department,
            'role_group': department,
            'business_email': contact.get('business_email') or contact.get('email'),
            'email': contact.get('email'),
            'phone': contact.get('phone'),
            'linkedin_url': contact.get('linkedin_url'),
            'source': contact.get('source') or 'Apollo',
        })
        if len(normalized) == MAX_CONTACTS_PER_HOTEL:
            break
    return normalized


def enrich_managers_bulk(hotels, api_key):
    results = []
    for hotel in hotels:
        try:
            provider_result = search_decision_makers(
                business=hotel,
                category=hotel.get('category', 'hotels_resorts'),
                api_key=api_key,
            )
            contacts = _normalize_contacts(provider_result.get('contacts'))
            provider_status = provider_result.get('status')
            result_status = provider_status if provider_status in {'PARTIAL', 'ERROR'} else (
                'FOUND' if contacts else 'NOT_FOUND'
            )
        except PeopleEnrichmentError:
            logger.exception('Apollo enrichment failed for %s.', hotel['name'])
            contacts = []
            result_status = 'ERROR'
        results.append({
            'business_name': hotel['name'],
            'hotel_name': hotel['name'],
            'category': hotel.get('category', 'hotels_resorts'),
            'status': result_status,
            'contacts': contacts,
        })

    summary = {
        'requested': len(hotels),
        'processed': len(results),
        'found': sum(result['status'] in {'FOUND', 'PARTIAL'} for result in results),
        'not_found': sum(result['status'] == 'NOT_FOUND' for result in results),
        'errors': sum(result['status'] == 'ERROR' for result in results),
    }
    return {'results': results, 'summary': summary}


def enrich_managers_multi_provider_bulk(hotels, providers, provider_settings):
    results = []
    for hotel in hotels:
        try:
            result = search_decision_makers_multi_provider(
                hotel, hotel.get('category', 'hotels_resorts'), providers, provider_settings
            )
        except PeopleEnrichmentError:
            result = {
                'business_name': hotel['name'], 'hotel_name': hotel['name'],
                'category': hotel.get('category', 'hotels_resorts'),
                'status': 'ERROR', 'contacts': [], 'providers': providers,
                'provider_results': {},
            }
        results.append(result)
    summary = {
        'requested': len(hotels), 'processed': len(results),
        'found': sum(result['status'] in {'FOUND', 'PARTIAL'} for result in results),
        'not_found': sum(result['status'] == 'NOT_FOUND' for result in results),
        'errors': sum(result['status'] == 'ERROR' for result in results),
    }
    return {'results': results, 'summary': summary, 'providers': providers}
