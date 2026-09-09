from django.conf import settings

from .apollo import _domain, _normalize, _role_match
from .base import PeopleEnrichmentConfigurationError, PeopleEnrichmentError
from .role_profiles import get_search_titles


class ZoomInfoTransportNotConfigured(PeopleEnrichmentConfigurationError):
    """The account-specific ZoomInfo API product transport is not configured."""


class ZoomInfoAccountTransport:
    """Boundary for an account-specific, documented ZoomInfo API implementation."""

    def search_organizations(self, **kwargs):
        raise ZoomInfoTransportNotConfigured(
            'ZoomInfo live transport requires account-specific API documentation.'
        )

    def search_people(self, **kwargs):
        raise ZoomInfoTransportNotConfigured(
            'ZoomInfo live transport requires account-specific API documentation.'
        )


class ZoomInfoPeopleEnrichmentProvider:
    def __init__(self, api_key=None, transport=None):
        self.api_key = api_key if api_key is not None else settings.ZOOMINFO_API_KEY
        if not self.api_key:
            raise PeopleEnrichmentConfigurationError('ZOOMINFO_API_KEY is not configured.')
        self.transport = transport or ZoomInfoAccountTransport()

    def match_organization(self, business):
        domain = _domain(business.get('website'))
        organizations = self.transport.search_organizations(
            api_key=self.api_key, domain=domain, name=business.get('brand') or business.get('name'),
            location=business.get('address') or business.get('location'), limit=5,
        )
        if not isinstance(organizations, list):
            raise PeopleEnrichmentError('ZoomInfo returned a malformed organization response.')
        for organization in organizations:
            if not isinstance(organization, dict):
                continue
            organization_domain = _domain(
                organization.get('domain') or organization.get('website')
            )
            if domain and organization_domain == domain:
                return organization
            if not domain and _normalize(organization.get('name')) in {
                _normalize(business.get('name')), _normalize(business.get('brand')),
            }:
                return organization
        return None

    def _normalize_contact(self, person, organization_name, category):
        role_group, priority = _role_match(person.get('title'), category)
        if not role_group:
            return None
        return {
            'provider_person_id': person.get('id') or person.get('person_id'),
            'name': person.get('name'), 'title': person.get('title'),
            'role_group': role_group, 'department': role_group,
            'organization_name': person.get('organization_name') or organization_name,
            'company': person.get('organization_name') or organization_name,
            'business_email': person.get('business_email') or person.get('email'),
            'email': person.get('business_email') or person.get('email'),
            'phone': person.get('phone'), 'linkedin_url': person.get('linkedin_url'),
            'source': 'ZoomInfo', 'verification_status': person.get('verification_status'),
            '_role_priority': priority,
        }

    def search_decision_makers(self, business, category='hotels_resorts'):
        organization = self.match_organization(business)
        if not organization or not (organization.get('id') or organization.get('company_id')):
            return _result(business, category, [], 'NOT_FOUND')
        people = self.transport.search_people(
            api_key=self.api_key,
            organization_id=organization.get('id') or organization.get('company_id'),
            titles=get_search_titles(category), limit=25, reveal_contacts=False,
        )
        if not isinstance(people, list):
            raise PeopleEnrichmentError('ZoomInfo returned a malformed people response.')
        contacts = []
        for person in people:
            if isinstance(person, dict):
                contact = self._normalize_contact(person, organization.get('name'), category)
                if contact:
                    contacts.append(contact)
        contacts.sort(key=lambda contact: contact.pop('_role_priority'))
        contacts = contacts[:3]
        useful = any(contact.get(field) for contact in contacts for field in (
            'business_email', 'phone', 'linkedin_url'
        ))
        return _result(
            business, category, contacts,
            'FOUND' if useful else 'PARTIAL' if contacts else 'NOT_FOUND',
        )


def _result(business, category, contacts, status):
    return {
        'business_name': business.get('name'), 'hotel_name': business.get('name'),
        'category': category, 'status': status, 'contacts': contacts,
    }
