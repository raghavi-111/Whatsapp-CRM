from urllib.parse import urlparse

import requests

from .base import HotelEnrichmentProvider


class ExistingDataWebsiteDiscoveryProvider(HotelEnrichmentProvider):
    """Discover a website only from attributable data already supplied."""

    def enrich(self, hotel):
        incoming_source = hotel.get('source')
        candidates = (
            ('website', incoming_source or 'OpenStreetMap', 'HIGH'),
            ('contact_website', (
                f'{incoming_source} contact:website'
                if incoming_source else 'OpenStreetMap contact:website'
            ), 'HIGH'),
            ('brand_website', 'Verified brand website', 'MEDIUM'),
            ('domain_hint', 'Existing hotel domain hint', 'MEDIUM'),
        )
        for field, source, confidence in candidates:
            value = hotel.get(field)
            if not value:
                continue
            try:
                parsed = urlparse(value)
            except ValueError:
                return {'website': value, 'source': source, 'confidence': 'LOW', 'status': 'ERROR'}
            if parsed.scheme in {'http', 'https'} and parsed.hostname:
                return {'website': value, 'source': source, 'confidence': confidence, 'status': 'FOUND'}
            return {'website': value, 'source': source, 'confidence': 'LOW', 'status': 'ERROR'}

        wikidata = hotel.get('wikidata')
        if wikidata and str(wikidata).upper().startswith('Q'):
            try:
                response = requests.get(
                    f'https://www.wikidata.org/wiki/Special:EntityData/{wikidata}.json',
                    headers={'User-Agent': 'HotelLeadCollector/0.1'},
                    timeout=8,
                )
                response.raise_for_status()
                claims = response.json()['entities'][wikidata]['claims'].get('P856', [])
                value = claims[0]['mainsnak']['datavalue']['value'] if claims else None
                parsed = urlparse(value) if value else None
                if parsed and parsed.scheme in {'http', 'https'} and parsed.hostname:
                    return {
                        'website': value,
                        'source': f'Wikidata {wikidata}',
                        'confidence': 'HIGH',
                        'status': 'FOUND',
                    }
            except (KeyError, TypeError, ValueError, requests.RequestException):
                pass
        return {'website': None, 'source': None, 'confidence': None, 'status': 'NOT_FOUND'}


def discover_official_website(
    hotel_name,
    address=None,
    brand=None,
    latitude=None,
    longitude=None,
    website=None,
    contact_website=None,
    brand_website=None,
    domain_hint=None,
    wikidata=None,
    wikipedia=None,
    source=None,
):
    hotel = {
        'name': hotel_name,
        'address': address,
        'brand': brand,
        'latitude': latitude,
        'longitude': longitude,
        'website': website,
        'contact_website': contact_website,
        'brand_website': brand_website,
        'domain_hint': domain_hint,
        'wikidata': wikidata,
        'wikipedia': wikipedia,
        'source': source,
    }
    return ExistingDataWebsiteDiscoveryProvider().enrich(hotel)
