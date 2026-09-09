import math
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlparse

from lead_collector.models import ProviderSettings
from lead_collector.provider_settings import get_business_providers, get_provider_settings
from lead_collector.services.openstreetmap import calculate_distance_km

from .factory import get_business_provider
from .base import UnsupportedBusinessCategoryError


PROVIDER_LABELS = {
    ProviderSettings.OPENSTREETMAP: 'OpenStreetMap',
    ProviderSettings.GEOAPIFY: 'Geoapify',
    ProviderSettings.GOOGLE: 'Google Places',
    ProviderSettings.PLAYWRIGHT: 'Browser Search',
}
PROVIDER_PRIORITY = ('google', 'geoapify', 'openstreetmap', 'playwright')
PRIORITY_RANK = {provider: index for index, provider in enumerate(PROVIDER_PRIORITY)}
DEDUPLICATION_DISTANCE_KM = 0.1
MERGE_FIELDS = (
    'address', 'latitude', 'longitude', 'distance_km', 'phone', 'email',
    'website', 'brand', 'stars', 'category', 'google_maps_url', 'wikidata',
    'wikipedia', 'contact_website', 'brand_website', 'rating', 'review_count',
    'opening_hours', 'maps_url',
)
GENERIC_NAMES = {
    'hospital', 'restaurant', 'hotel', 'resort', 'cafe', 'school', 'university',
    'college', 'bank', 'pharmacy', 'hostel', 'gym', 'salon', 'spa', 'store',
}
logger = logging.getLogger(__name__)


class MultiProviderSearchError(Exception):
    """Raised when no selected provider can return a result."""


class InvalidProviderSelectionError(Exception):
    """Raised when a request selects a provider not enabled in Settings."""


def normalize_name(value):
    if not value:
        return ''
    value = unicodedata.normalize('NFKC', str(value)).casefold().strip()
    value = ''.join(
        ' ' if unicodedata.category(character).startswith('P') else character
        for character in value
    )
    return ' '.join(value.split())


def normalize_domain(value):
    if not value:
        return ''
    candidate = str(value).strip()
    parsed = urlparse(candidate if '://' in candidate else f'//{candidate}')
    domain = (parsed.hostname or '').casefold().rstrip('.')
    return domain[4:] if domain.startswith('www.') else domain


def _normalized_address(value):
    return re.sub(r'[^\w]+', ' ', str(value or '').casefold()).strip()


def _similar(first, second, threshold=0.84):
    return bool(first and second and SequenceMatcher(None, first, second).ratio() >= threshold)


def _separation(first, second):
    return calculate_distance_km(
        first.get('latitude'), first.get('longitude'),
        second.get('latitude'), second.get('longitude'),
    )


def _is_duplicate(first, second):
    first_domain = normalize_domain(first.get('website'))
    second_domain = normalize_domain(second.get('website'))
    if first_domain and first_domain == second_domain:
        return True

    first_name = normalize_name(first.get('name'))
    second_name = normalize_name(second.get('name'))
    if not _similar(first_name, second_name) or (
        first_name in GENERIC_NAMES and second_name in GENERIC_NAMES
    ):
        return False

    distance = _separation(first, second)
    if distance is not None and distance <= DEDUPLICATION_DISTANCE_KM:
        return True

    first_address = _normalized_address(first.get('address'))
    second_address = _normalized_address(second.get('address'))
    return _similar(first_address, second_address, threshold=0.9)


def _provider_id(record):
    source = record.get('_provider')
    if source in PROVIDER_LABELS:
        return source
    label = record.get('source')
    return next((key for key, value in PROVIDER_LABELS.items() if value == label), '')


def _provider_from_label(label):
    return next((key for key, value in PROVIDER_LABELS.items() if value == label), '')


def _normalize_record(record, provider, category, origin_latitude, origin_longitude):
    normalized = dict(record) if isinstance(record, dict) else {}
    normalized['_provider'] = provider
    normalized['source'] = PROVIDER_LABELS[provider]
    normalized['sources'] = [PROVIDER_LABELS[provider]]
    normalized['category'] = normalized.get('category') or category
    if normalized.get('distance_km') is None:
        normalized['distance_km'] = calculate_distance_km(
            origin_latitude, origin_longitude,
            normalized.get('latitude'), normalized.get('longitude'),
        )
    for field in ('name',) + MERGE_FIELDS:
        normalized.setdefault(field, None)
        if normalized.get(field) not in (None, ''):
            normalized[f'{field}_source'] = PROVIDER_LABELS[provider]
    return normalized


def _merge(first, second):
    merged = first.copy()
    sources = list(dict.fromkeys(first.get('sources', []) + second.get('sources', [])))
    merged['sources'] = sorted(
        sources,
        key=lambda label: PRIORITY_RANK.get(
            next((key for key, value in PROVIDER_LABELS.items() if value == label), ''), 99
        ),
    )
    merged['source'] = ' + '.join(merged['sources'])

    for field in ('name',) + MERGE_FIELDS:
        first_value, second_value = merged.get(field), second.get(field)
        if second_value in (None, ''):
            continue
        first_provider = _provider_from_label(merged.get(f'{field}_source')) or _provider_id(first)
        second_provider = _provider_id(second)
        if first_value in (None, '') or PRIORITY_RANK.get(second_provider, 99) < PRIORITY_RANK.get(first_provider, 99):
            merged[field] = second_value
            merged[f'{field}_source'] = PROVIDER_LABELS[second_provider]
    merged['_provider'] = min(
        (_provider_id(first), _provider_id(second)), key=lambda item: PRIORITY_RANK.get(item, 99)
    )
    return merged


def deduplicate_businesses(records):
    merged = []
    for record in records:
        duplicate_index = next(
            (index for index, existing in enumerate(merged) if _is_duplicate(existing, record)),
            None,
        )
        if duplicate_index is None:
            merged.append(record)
        else:
            merged[duplicate_index] = _merge(merged[duplicate_index], record)
    for record in merged:
        record.pop('_provider', None)
    return sorted(
        merged,
        key=lambda record: (
            record.get('distance_km') is None,
            record.get('distance_km') if isinstance(record.get('distance_km'), (int, float))
            and math.isfinite(record['distance_km']) else math.inf,
        ),
    )


def search_businesses_multi_provider(
    latitude, longitude, radius, category, providers=None, provider_settings=None,
    search_depth='standard',
):
    provider_settings = provider_settings or get_provider_settings()
    selected = list(dict.fromkeys(providers or get_business_providers(provider_settings)))
    valid = set(PROVIDER_LABELS)
    if not selected or any(provider not in valid for provider in selected):
        raise InvalidProviderSelectionError('Select at least one valid business data provider.')
    enabled = set(get_business_providers(provider_settings))
    if providers is not None and any(provider not in enabled for provider in selected):
        raise InvalidProviderSelectionError(
            'One or more selected business data providers are not enabled in Settings.'
        )

    records = []
    provider_results = {}
    failures = []
    for provider_name in selected:
        try:
            provider = get_business_provider(provider_name, provider_settings)
            search_kwargs = dict(
                latitude=latitude, longitude=longitude, radius=radius, category=category,
            )
            if provider_name == ProviderSettings.PLAYWRIGHT:
                search_kwargs['search_depth'] = search_depth
            results = provider.search_nearby_businesses(**search_kwargs)
            normalized = [
                _normalize_record(result, provider_name, category, latitude, longitude)
                for result in results
            ]
            records.extend(normalized)
            provider_results[provider_name] = {'status': 'success', 'count': len(normalized)}
        except Exception as exc:
            failures.append(exc)
            provider_results[provider_name] = {'status': 'error'}
            # Record the provider and exception type without serializing
            # credential-bearing messages or URLs into API diagnostics.
            logger.warning(
                'Lead Collector provider %s failed (%s).', provider_name, type(exc).__name__
            )

    if not any(result['status'] == 'success' for result in provider_results.values()):
        if failures and all(isinstance(exc, UnsupportedBusinessCategoryError) for exc in failures):
            raise failures[0]
        raise MultiProviderSearchError('Unable to retrieve hotel data at this time.')

    businesses = deduplicate_businesses(records)
    return {
        'hotels': businesses,
        'providers': selected,
        'provider_results': provider_results,
        'raw_result_count': len(records),
        'deduplicated_count': len(businesses),
    }
