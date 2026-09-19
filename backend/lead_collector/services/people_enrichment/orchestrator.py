import re

from lead_collector.provider_settings import get_people_providers, get_provider_settings

from .base import PeopleEnrichmentError
from .providers import get_people_provider
from .role_profiles import get_role_profile


PEOPLE_PROVIDER_LABELS = {
    'official_website': 'Official Website', 'apollo': 'Apollo', 'zoominfo': 'ZoomInfo',
}
# Deterministic fallback only when providers expose no comparable verification signal.
PEOPLE_PROVIDER_PRIORITY = ('apollo', 'zoominfo', 'official_website')
PRIORITY = {provider: index for index, provider in enumerate(PEOPLE_PROVIDER_PRIORITY)}
CONTACT_FIELDS = (
    'name', 'title', 'role_group', 'organization_name', 'business_email', 'phone',
    'linkedin_url', 'source_url', 'confidence',
)
VERIFIED_VALUES = {'verified', 'valid', 'validated', 'confirmed'}


class InvalidPeopleProviderSelection(PeopleEnrichmentError):
    pass


def _normalized(value):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', str(value or '').casefold()).split())


def _linkedin(value):
    return str(value or '').casefold().rstrip('/').replace('http://', 'https://')


def _same_person(first, second):
    first_email, second_email = _normalized(first.get('business_email')), _normalized(second.get('business_email'))
    if first_email and first_email == second_email:
        return True
    first_linkedin, second_linkedin = _linkedin(first.get('linkedin_url')), _linkedin(second.get('linkedin_url'))
    if first_linkedin and first_linkedin == second_linkedin:
        return True
    identity_fields = ('name', 'title', 'organization_name')
    if all(_normalized(first.get(field)) and _normalized(first.get(field)) == _normalized(second.get(field))
           for field in identity_fields):
        return True
    return first.get('_provider') == second.get('_provider') and bool(
        first.get('provider_person_id') and first.get('provider_person_id') == second.get('provider_person_id')
    )


def _verified(contact):
    return _normalized(contact.get('verification_status')) in VERIFIED_VALUES


def _merge(first, second):
    merged = first.copy()
    merged['sources'] = list(dict.fromkeys(first['sources'] + second['sources']))
    merged['source'] = ' + '.join(merged['sources'])
    for field in CONTACT_FIELDS:
        candidate = second.get(field)
        if candidate in (None, ''):
            continue
        current = merged.get(field)
        choose = current in (None, '') or (_verified(second) and not _verified(merged))
        if not choose and current != candidate:
            current_provider = merged.get(f'{field}_provider', merged.get('_provider'))
            choose = PRIORITY.get(second['_provider'], 99) < PRIORITY.get(current_provider, 99)
            if field in {'business_email', 'phone'}:
                alternatives = merged.setdefault(f'{field}_alternatives', [])
                if candidate not in alternatives and candidate != current:
                    alternatives.append(candidate)
        if choose:
            merged[field] = candidate
            merged[f'{field}_source'] = PEOPLE_PROVIDER_LABELS[second['_provider']]
            merged[f'{field}_provider'] = second['_provider']
    return merged


def _role_rank(contact, category):
    if contact.get('role_group') == 'general_manager':
        return 0
    if contact.get('role_group') == 'sales':
        return 1
    profile = get_role_profile(category)
    groups = list(profile)
    try:
        role_group = contact.get('role_group')
        if role_group == 'IT':
            role_group = 'IT Leadership'
        return groups.index(role_group)
    except ValueError:
        return len(groups)


def search_decision_makers_multi_provider(
    business, category, providers=None, provider_settings=None,
):
    provider_settings = provider_settings or get_provider_settings()
    enabled = get_people_providers(provider_settings)
    selected = list(dict.fromkeys(enabled if providers is None else providers))
    if any(provider not in PEOPLE_PROVIDER_LABELS for provider in selected):
        raise InvalidPeopleProviderSelection('An invalid people provider was selected.')
    if any(provider not in enabled for provider in selected):
        raise InvalidPeopleProviderSelection('A selected people provider is not enabled in Settings.')
    if not selected:
        raise InvalidPeopleProviderSelection('Configure a people enrichment provider in Settings.')

    contacts, provider_results = [], {}
    for provider_name in selected:
        try:
            result = get_people_provider(provider_name, provider_settings).search_decision_makers(
                business, category
            )
            normalized = []
            for raw_contact in result.get('contacts') or []:
                if not isinstance(raw_contact, dict):
                    continue
                contact = {field: raw_contact.get(field) for field in CONTACT_FIELDS}
                contact.update({
                    'provider_person_id': raw_contact.get('provider_person_id'),
                    'verification_status': raw_contact.get('verification_status'),
                    'department': raw_contact.get('department') or raw_contact.get('role_group'),
                    'email': raw_contact.get('business_email') or raw_contact.get('email'),
                    'source': PEOPLE_PROVIDER_LABELS[provider_name],
                    'sources': [PEOPLE_PROVIDER_LABELS[provider_name]], '_provider': provider_name,
                })
                for field in CONTACT_FIELDS:
                    if contact.get(field) not in (None, ''):
                        contact[f'{field}_source'] = PEOPLE_PROVIDER_LABELS[provider_name]
                        contact[f'{field}_provider'] = provider_name
                normalized.append(contact)
            contacts.extend(normalized)
            provider_results[provider_name] = {'status': 'success', 'count': len(normalized)}
        except Exception:
            provider_results[provider_name] = {'status': 'error'}

    if not any(result['status'] == 'success' for result in provider_results.values()):
        return _result(business, category, selected, provider_results, [], 'ERROR')
    merged = []
    for contact in contacts:
        index = next((i for i, existing in enumerate(merged) if _same_person(existing, contact)), None)
        if index is None:
            merged.append(contact)
        else:
            merged[index] = _merge(merged[index], contact)
    merged.sort(key=lambda contact: _role_rank(contact, category))
    for contact in merged:
        for key in [key for key in contact if key == '_provider' or key.endswith('_provider')]:
            contact.pop(key, None)
    merged = merged[:3]
    status = 'FOUND' if any(contact.get(field) for contact in merged for field in ('business_email', 'phone', 'linkedin_url')) else 'PARTIAL' if merged else 'NOT_FOUND'
    return _result(business, category, selected, provider_results, merged, status)


def _result(business, category, providers, provider_results, contacts, status):
    return {
        'business_name': business.get('name'), 'hotel_name': business.get('name'),
        'category': category, 'status': status, 'contacts': contacts,
        'providers': providers, 'provider_results': provider_results,
    }
