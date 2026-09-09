import re
from urllib.parse import urlparse

import requests
from django.conf import settings

from .base import (
    PeopleEnrichmentConfigurationError,
    PeopleEnrichmentError,
    PeopleEnrichmentProvider,
)
from .role_profiles import get_role_profile, get_search_titles


ORGANIZATION_SEARCH_URL = 'https://api.apollo.io/api/v1/mixed_companies/search'
PEOPLE_SEARCH_URL = 'https://api.apollo.io/api/v1/mixed_people/api_search'
PERSON_ENRICH_URL = 'https://api.apollo.io/api/v1/people/match'
REQUEST_TIMEOUT_SECONDS = 15
MAX_CONTACTS = 3

PREFERRED_SENIORITIES = ('owner', 'founder', 'c_suite', 'vp', 'director', 'head', 'manager')


def _normalize(value):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', (value or '').casefold()).split())


def _domain(website):
    if not website:
        return None
    value = str(website).strip()
    parsed = urlparse(value if '://' in value else f'//{value}')
    hostname = (parsed.hostname or '').casefold().removeprefix('www.').rstrip('.')
    if not hostname or not re.fullmatch(r'[a-z0-9.-]+', hostname):
        return None
    return hostname


def _title_tokens(value):
    normalized = _normalize(value)
    normalized = re.sub(r'\binformation technology\b', 'it', normalized)
    return tuple(sorted(token for token in normalized.split() if token not in {'of', 'and', 'the'}))


def _role_match(title, category):
    candidate = _title_tokens(title)
    for role_group, approved_titles in get_role_profile(category).items():
        for priority, approved in enumerate(approved_titles):
            if candidate == _title_tokens(approved):
                return role_group, priority
    return None, None


def _role_group(title, category):
    return _role_match(title, category)[0]


def _legacy_department(role_group, category):
    if category == 'hotels_resorts' and role_group in {'IT', 'IT Leadership', 'IT Management'}:
        return 'Information Technology'
    return role_group


def _headers(api_key):
    return {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Api-Key': api_key,
    }


def _request_json(url, api_key, params):
    try:
        response = requests.post(
            url,
            headers=_headers(api_key),
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise PeopleEnrichmentError('The Apollo request timed out.') from exc
    except requests.RequestException as exc:
        raise PeopleEnrichmentError('Could not connect to Apollo.') from exc
    if response.status_code in {401, 403}:
        raise PeopleEnrichmentError(
            'Apollo API access is not available for the configured account or key.'
        )
    if response.status_code == 429:
        raise PeopleEnrichmentError('Apollo quota or rate limit was reached; credits may be unavailable.')
    if response.status_code >= 500:
        raise PeopleEnrichmentError('Apollo is temporarily unavailable.')
    if response.status_code != 200:
        raise PeopleEnrichmentError('Apollo returned an unexpected response.')
    try:
        data = response.json()
    except ValueError as exc:
        raise PeopleEnrichmentError('Apollo returned invalid JSON.') from exc
    if not isinstance(data, dict):
        raise PeopleEnrichmentError('Apollo returned a malformed response.')
    return data


class ApolloPeopleEnrichmentProvider(PeopleEnrichmentProvider):
    def __init__(self, api_key=None):
        self.api_key = api_key if api_key is not None else settings.APOLLO_API_KEY
        if not self.api_key:
            raise PeopleEnrichmentConfigurationError('APOLLO_API_KEY is not configured.')

    def match_organization(
        self, business, website=None, brand=None, location=None,
    ):
        if isinstance(business, str):
            business = {
                'name': business, 'website': website,
                'brand': brand, 'address': location,
            }
        business_name = business.get('name')
        website = business.get('website')
        brand = business.get('brand')
        location = business.get('address') or business.get('location')
        domain = _domain(website)
        params = {'page': 1, 'per_page': 5}
        if domain:
            params['q_organization_domains_list[]'] = domain
        else:
            params['q_organization_name'] = brand or business_name
        if location:
            params['organization_locations[]'] = location

        data = _request_json(ORGANIZATION_SEARCH_URL, self.api_key, params)
        organizations = data.get('organizations')
        if not isinstance(organizations, list):
            raise PeopleEnrichmentError('Apollo returned a malformed organization response.')

        for organization in organizations:
            if not isinstance(organization, dict):
                continue
            organization_domain = (organization.get('primary_domain') or organization.get('website_url') or '')
            organization_domain = _domain(organization_domain) or organization_domain.removeprefix('www.')
            if domain and organization_domain == domain:
                return organization
            if not domain and _normalize(organization.get('name')) in {
                _normalize(business_name), _normalize(brand)
            }:
                return organization
        return None

    def search_people(self, organization_id, category, domain=None, location=None):
        params = {
            'organization_ids[]': organization_id,
            'person_titles[]': get_search_titles(category),
            'person_seniorities[]': PREFERRED_SENIORITIES,
            'include_similar_titles': 'false',
            'page': 1,
            'per_page': 25,
        }
        if domain:
            params['q_organization_domains_list[]'] = domain
        if location:
            params['person_locations[]'] = location
        data = _request_json(PEOPLE_SEARCH_URL, self.api_key, params)
        people = data.get('people')
        if not isinstance(people, list):
            raise PeopleEnrichmentError('Apollo returned a malformed people response.')
        return people

    def _select_people(self, people, category='hotels_resorts'):
        best_by_group = {}
        for sequence, person in enumerate(people):
            if not isinstance(person, dict):
                continue
            role_group, title_priority = _role_match(person.get('title'), category)
            if not role_group:
                continue
            current = best_by_group.get(role_group)
            if current is None or (title_priority, sequence) < current[:2]:
                best_by_group[role_group] = (title_priority, sequence, person)
        return [
            best_by_group[group][2]
            for group in get_role_profile(category)
            if group in best_by_group
        ][:MAX_CONTACTS]

    def enrich_person(self, person, organization_name, domain=None):
        params = {
            'id': person.get('id') or person.get('person_id'),
            'name': person.get('name'),
            'organization_name': organization_name,
            'domain': domain,
            'reveal_personal_emails': 'false',
            'reveal_phone_number': 'false',
        }
        params = {key: value for key, value in params.items() if value}
        data = _request_json(PERSON_ENRICH_URL, self.api_key, params)
        enriched = data.get('person')
        if enriched is None:
            enriched = person
        if not isinstance(enriched, dict):
            raise PeopleEnrichmentError('Apollo returned a malformed person response.')
        return enriched

    def _normalize_contact(
        self, person, fallback, organization_name, category='hotels_resorts',
    ):
        title = person.get('title') or fallback.get('title')
        role_group = _role_group(title, category)
        if not role_group:
            return None
        contact_role_group = 'IT' if role_group in {'IT Leadership', 'IT Management'} else role_group

        phone = None
        for phone_record in person.get('phone_numbers') or []:
            if isinstance(phone_record, dict) and phone_record.get('type') in {'work', 'work_direct'}:
                phone = phone_record.get('sanitized_number') or phone_record.get('raw_number')
                if phone:
                    break
        return {
            'provider_person_id': person.get('id') or fallback.get('id'),
            'name': person.get('name') or fallback.get('name'),
            'title': title,
            'role_group': contact_role_group,
            'department': _legacy_department(role_group, category),
            'company': (person.get('organization') or {}).get('name') or organization_name,
            'organization_name': (person.get('organization') or {}).get('name') or organization_name,
            'first_name': person.get('first_name') or fallback.get('first_name'),
            'last_name': person.get('last_name') or fallback.get('last_name'),
            'business_email': person.get('email'),
            'email': person.get('email'),
            'phone': phone,
            'linkedin_url': person.get('linkedin_url'),
            'source': 'Apollo',
            'verification_status': 'FOUND',
        }

    def search_decision_makers(self, business, category='hotels_resorts'):
        if isinstance(business, str):
            business = {'name': business}
        try:
            get_role_profile(category)
        except ValueError as exc:
            raise PeopleEnrichmentError(str(exc)) from exc
        business_name = business.get('name')
        organization = self.match_organization(business)
        if not organization or not organization.get('id'):
            return _result(business_name, category, None, [], 'NOT_FOUND')

        domain = _domain(business.get('website'))
        candidates = self._select_people(
            self.search_people(
                organization['id'], category, domain,
                business.get('address') or business.get('location'),
            ),
            category,
        )
        contacts = []
        for candidate in candidates:
            enriched = self.enrich_person(
                candidate, organization.get('name') or business_name, domain
            )
            contact = self._normalize_contact(
                enriched, candidate, organization.get('name') or business_name, category
            )
            if contact:
                contacts.append(contact)
        useful_contact = any(
            contact.get(field)
            for contact in contacts
            for field in ('business_email', 'phone', 'linkedin_url')
        )
        status = 'FOUND' if useful_contact else 'PARTIAL' if contacts else 'NOT_FOUND'
        return _result(business_name, category, organization, contacts, status)


def _result(business_name, category, organization, contacts, status):
    organization_result = None
    if organization:
        organization_result = {
            'name': organization.get('name'),
            'domain': _domain(
                organization.get('primary_domain') or organization.get('website_url')
            ),
        }
    return {
        'business_name': business_name,
        'hotel_name': business_name,
        'category': category,
        'status': status,
        'organization': organization_result,
        'contacts': contacts,
    }


def search_decision_makers(
    business=None, category='hotels_resorts', api_key=None, *,
    hotel_name=None, website=None, brand=None, location=None,
):
    """Search generic business decision-makers while accepting legacy hotel args."""
    if isinstance(business, str):
        business = {'name': business}
    business = dict(business or {})
    if hotel_name is not None:
        business.setdefault('name', hotel_name)
    if website is not None:
        business.setdefault('website', website)
    if brand is not None:
        business.setdefault('brand', brand)
    if location is not None:
        business.setdefault('address', location)
    return ApolloPeopleEnrichmentProvider(api_key=api_key).search_decision_makers(
        business, category
    )
