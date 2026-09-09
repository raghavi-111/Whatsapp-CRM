import hashlib
import re
import unicodedata

import requests
from django.conf import settings
from django.core.cache import cache


USER_AGENT = 'HotelLeadCollector/0.1 (location search)'
REQUEST_TIMEOUT_SECONDS = 10
PROVIDER_RESULT_LIMIT = 20
RESULT_LIMIT = 8
CACHE_SECONDS = 30 * 60


class NominatimError(Exception):
    """Raised when the configured geocoding service cannot complete a search."""


def _cache_key(query):
    digest = hashlib.sha256(query.casefold().encode()).hexdigest()
    return f'nominatim-search:v2:{digest}'


def _normalize_result(result):
    if not isinstance(result, dict):
        return None
    try:
        latitude = float(result['lat'])
        longitude = float(result['lon'])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    display_name = result.get('display_name')
    if not display_name:
        return None
    name = result.get('name') or display_name.split(',', 1)[0].strip()
    address = result.get('address') if isinstance(result.get('address'), dict) else {}
    secondary_parts = []
    for field in ('city', 'town', 'municipality', 'county', 'state', 'country'):
        value = address.get(field)
        if value and _normalized_text(value) != _normalized_text(name) and value not in secondary_parts:
            secondary_parts.append(value)
    try:
        importance = float(result.get('importance') or 0)
    except (TypeError, ValueError, OverflowError):
        importance = 0
    return {
        'name': name,
        'display_name': display_name,
        'secondary_name': ', '.join(secondary_parts[:2]),
        'latitude': latitude,
        'longitude': longitude,
        'type': result.get('type'),
        'class': result.get('class'),
        'provider_id': result.get('place_id'),
        'importance': importance,
    }


def _normalized_text(value):
    text = unicodedata.normalize('NFKD', str(value or '')).casefold()
    return ' '.join(re.findall(r'[\w]+', text, flags=re.UNICODE))


def _result_score(result, query):
    normalized_query = _normalized_text(query)
    name = _normalized_text(result['name'])
    display = _normalized_text(result['display_name'])
    if name == normalized_query:
        relevance = 1000
    elif name.startswith(normalized_query):
        relevance = 800
    elif any(token.startswith(normalized_query) for token in name.split()):
        relevance = 650
    elif normalized_query in name:
        relevance = 450
    elif normalized_query in display:
        relevance = 250
    else:
        relevance = 0
    useful_types = {'city', 'town', 'municipality', 'administrative', 'suburb', 'neighbourhood', 'village', 'locality', 'aerodrome', 'airport'}
    type_bonus = 35 if _normalized_text(result.get('type')) in useful_types else 0
    return relevance + type_bonus + min(max(result.get('importance', 0), 0), 1) * 100


def rank_location_results(results, query, limit=RESULT_LIMIT):
    unique, provider_ids, signatures = [], set(), set()
    for result in results:
        provider_id = result.get('provider_id')
        signature = (_normalized_text(result.get('display_name')), round(result['latitude'], 6), round(result['longitude'], 6))
        if (provider_id is not None and provider_id in provider_ids) or signature in signatures:
            continue
        if provider_id is not None:
            provider_ids.add(provider_id)
        signatures.add(signature)
        unique.append(result)
    return sorted(unique, key=lambda item: (-_result_score(item, query), -item.get('importance', 0), _normalized_text(item['display_name'])))[:limit]


def search_locations(query):
    cache_key = _cache_key(query)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            settings.NOMINATIM_API_URL,
            params={
                'q': query,
                'format': 'json',
                'limit': PROVIDER_RESULT_LIMIT,
                'addressdetails': 1,
            },
            headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise NominatimError('The location search timed out.') from exc
    except requests.ConnectionError as exc:
        raise NominatimError('Could not connect to the location search service.') from exc
    except requests.RequestException as exc:
        raise NominatimError('The location search request failed.') from exc

    if response.status_code == 429:
        raise NominatimError('The location search rate limit was reached.')
    if 500 <= response.status_code <= 599:
        raise NominatimError('The location search service is temporarily unavailable.')
    if response.status_code != 200:
        raise NominatimError(
            f'The location search service returned HTTP {response.status_code}.'
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise NominatimError('The location search service returned invalid JSON.') from exc
    if not isinstance(data, list):
        raise NominatimError('The location search service returned a malformed response.')

    normalized_results = [normalized for item in data if (normalized := _normalize_result(item))]
    results = rank_location_results(normalized_results, query)
    cache.set(cache_key, results, CACHE_SECONDS)
    return results
