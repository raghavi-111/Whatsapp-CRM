import logging
import math
import unicodedata

import requests
from django.conf import settings
from django.core.cache import cache

from ..business_categories import get_business_category


logger = logging.getLogger(__name__)

DEFAULT_OVERPASS_API_URL = 'https://overpass-api.de/api/interpreter'
DEFAULT_OVERPASS_FALLBACK_URL = 'https://overpass.kumi.systems/api/interpreter'
MAX_RADIUS_METERS = 20_000
REQUEST_TIMEOUT_SECONDS = 30
USER_AGENT = 'HotelLeadCollector/0.1'
CACHE_TIMEOUT_SECONDS = 30 * 60
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
DEDUPLICATION_DISTANCE_KM = 0.15
COMPLETENESS_FIELDS = ('address', 'phone', 'email', 'website', 'brand', 'stars')


class OpenStreetMapError(Exception):
    """Raised when validation or an Overpass request fails."""

    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def _number(value, field_name):
    if value is None or isinstance(value, bool):
        raise OpenStreetMapError(f'{field_name} is required and must be numeric.')
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise OpenStreetMapError(f'{field_name} is required and must be numeric.') from exc


def _validate_search(latitude, longitude, radius):
    latitude = _number(latitude, 'Latitude')
    longitude = _number(longitude, 'Longitude')
    radius = _number(radius, 'Radius')

    if not -90 <= latitude <= 90:
        raise OpenStreetMapError('Latitude must be between -90 and 90.')
    if not -180 <= longitude <= 180:
        raise OpenStreetMapError('Longitude must be between -180 and 180.')
    if radius <= 0:
        raise OpenStreetMapError('Radius must be positive.')
    if radius > MAX_RADIUS_METERS:
        raise OpenStreetMapError(
            f'Radius must not exceed {MAX_RADIUS_METERS} meters.'
        )

    return latitude, longitude, radius


def _first_non_empty(tags, *keys):
    for key in keys:
        value = tags.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _build_address(tags):
    house_number = _first_non_empty(tags, 'addr:housenumber')
    street = _first_non_empty(tags, 'addr:street')
    street_address = ' '.join(
        str(value).strip() for value in (house_number, street) if value
    )

    parts = [street_address] if street_address else []
    for key in ('addr:suburb', 'addr:city', 'addr:state', 'addr:postcode'):
        value = _first_non_empty(tags, key)
        if value:
            parts.append(str(value).strip())
    return ', '.join(parts) or None


def _coordinates(element):
    if element.get('type') == 'node':
        return element.get('lat'), element.get('lon')
    center = element.get('center') or {}
    return center.get('lat'), center.get('lon')


def _normalize_element(element):
    if not isinstance(element, dict):
        return None
    osm_type = element.get('type')
    osm_id = element.get('id')
    if osm_type not in {'node', 'way', 'relation'} or osm_id is None:
        return None

    tags = element.get('tags') or {}
    if not isinstance(tags, dict):
        return None
    latitude, longitude = _coordinates(element)

    return {
        'id': f'{osm_type}/{osm_id}',
        'osm_type': osm_type,
        'osm_id': osm_id,
        'name': _first_non_empty(tags, 'name'),
        'address': _build_address(tags),
        'latitude': latitude,
        'longitude': longitude,
        'phone': _first_non_empty(tags, 'phone', 'contact:phone'),
        'email': _first_non_empty(tags, 'email', 'contact:email'),
        'website': _first_non_empty(tags, 'website', 'contact:website'),
        'contact_website': _first_non_empty(tags, 'contact:website'),
        'brand_website': _first_non_empty(tags, 'brand:website'),
        'brand': _first_non_empty(tags, 'brand'),
        'wikidata': _first_non_empty(tags, 'wikidata'),
        'wikipedia': _first_non_empty(tags, 'wikipedia'),
        'stars': _first_non_empty(tags, 'stars'),
        'source': 'OpenStreetMap',
    }


def _distance_km(origin_lat, origin_lng, destination_lat, destination_lng):
    try:
        coordinates = tuple(float(value) for value in (
            origin_lat, origin_lng, destination_lat, destination_lng
        ))
    except (TypeError, ValueError, OverflowError):
        return None

    if not all(math.isfinite(value) for value in coordinates):
        return None

    origin_lat, origin_lng, destination_lat, destination_lng = map(
        math.radians, coordinates
    )
    latitude_delta = destination_lat - origin_lat
    longitude_delta = destination_lng - origin_lng
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(origin_lat)
        * math.cos(destination_lat)
        * math.sin(longitude_delta / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(haversine)))


def calculate_distance_km(origin_lat, origin_lng, hotel_lat, hotel_lng):
    """Calculate Haversine distance in kilometres, rounded to two decimals."""
    distance = _distance_km(origin_lat, origin_lng, hotel_lat, hotel_lng)
    return round(distance, 2) if distance is not None else None


def _normalize_hotel_name(name):
    if not name:
        return None
    normalized = unicodedata.normalize('NFKC', str(name)).casefold().strip()
    normalized = ''.join(
        ' ' if unicodedata.category(character).startswith('P') else character
        for character in normalized
    )
    return ' '.join(normalized.split()) or None


def _completeness_score(hotel):
    return sum(bool(hotel.get(field)) for field in COMPLETENESS_FIELDS)


def _merge_duplicate(first, second):
    if _completeness_score(second) > _completeness_score(first):
        primary, secondary = second.copy(), first
    else:
        primary, secondary = first.copy(), second

    for field in COMPLETENESS_FIELDS:
        if not primary.get(field) and secondary.get(field):
            primary[field] = secondary[field]
    return primary


def _deduplicate_hotels(hotels):
    unique_hotels = []
    normalized_names = []

    for hotel in hotels:
        normalized_name = _normalize_hotel_name(hotel.get('name'))
        duplicate_index = None
        if normalized_name and hotel.get('latitude') is not None and hotel.get('longitude') is not None:
            for index, existing in enumerate(unique_hotels):
                if normalized_names[index] != normalized_name:
                    continue
                separation = _distance_km(
                    hotel['latitude'], hotel['longitude'],
                    existing.get('latitude'), existing.get('longitude'),
                )
                if separation is not None and separation <= DEDUPLICATION_DISTANCE_KM:
                    duplicate_index = index
                    break

        if duplicate_index is None:
            unique_hotels.append(hotel)
            normalized_names.append(normalized_name)
        else:
            unique_hotels[duplicate_index] = _merge_duplicate(
                unique_hotels[duplicate_index], hotel
            )

    return unique_hotels


def _add_distances_and_sort(hotels, origin_latitude, origin_longitude):
    for hotel in hotels:
        hotel['distance_km'] = calculate_distance_km(
            origin_latitude,
            origin_longitude,
            hotel.get('latitude'),
            hotel.get('longitude'),
        )
    return sorted(
        hotels,
        key=lambda hotel: (
            hotel['distance_km'] is None,
            hotel['distance_km'] if hotel['distance_km'] is not None else math.inf,
        ),
    )


def _build_overpass_query(latitude, longitude, radius, osm_tags):
    statements = []
    for rule in osm_tags:
        key = rule['key']
        if rule.get('match') == 'exists':
            selector = f'["{key}"]'
        else:
            selector = f'["{key}"="{rule["value"]}"]'
        for element_type in ('node', 'way', 'relation'):
            statements.append(
                f'  {element_type}{selector}'
                f'(around:{radius:g},{latitude:g},{longitude:g});'
            )
    return '[out:json][timeout:25];\n(\n' + '\n'.join(statements) + '\n);\nout center tags;'


def _build_query(latitude, longitude, radius):
    """Backward-compatible hotel query builder."""
    category = get_business_category('hotels_resorts')
    return _build_overpass_query(latitude, longitude, radius, category['osm_tags'])


def _configured_endpoints():
    configured = list(getattr(settings, 'OVERPASS_API_URLS', ()) or ())
    if not configured:
        legacy = getattr(settings, 'OVERPASS_API_URL', '')
        configured = [legacy] if legacy else []
        configured.extend((DEFAULT_OVERPASS_API_URL, DEFAULT_OVERPASS_FALLBACK_URL))
    unique = []
    for endpoint in configured:
        endpoint = str(endpoint).strip()
        if endpoint and endpoint not in unique:
            unique.append(endpoint)
    return unique[:2]


def _cache_key(latitude, longitude, radius, category='hotels_resorts'):
    return (
        f'business-search:osm:{category}:'
        f'{latitude:.6f}:{longitude:.6f}:{radius:.2f}'
    )


def _request_overpass(endpoint, query):
    try:
        response = requests.post(
            endpoint,
            data={'data': query},
            headers={'User-Agent': USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise OpenStreetMapError('The Overpass API request timed out.', retryable=True) from exc
    except requests.ConnectionError as exc:
        raise OpenStreetMapError('Could not connect to the Overpass API.', retryable=True) from exc
    except requests.RequestException as exc:
        raise OpenStreetMapError('The Overpass API request failed.') from exc

    if response.status_code in RETRYABLE_STATUS_CODES:
        message = (
            'The Overpass API rate limit was reached.' if response.status_code == 429
            else f'The Overpass API is unavailable (HTTP {response.status_code}).'
        )
        raise OpenStreetMapError(message, retryable=True)
    if 500 <= response.status_code <= 599:
        raise OpenStreetMapError(
            f'The Overpass API is unavailable (HTTP {response.status_code}).'
        )
    if response.status_code != 200:
        raise OpenStreetMapError(
            f'The Overpass API returned an unexpected HTTP {response.status_code} response.'
        )
    return response


def search_nearby_businesses(
    latitude, longitude, radius, category='hotels_resorts',
):
    """Return normalized OSM businesses for one trusted category."""
    latitude, longitude, radius = _validate_search(latitude, longitude, radius)
    try:
        category_config = get_business_category(category)
    except ValueError as exc:
        raise OpenStreetMapError(str(exc)) from exc
    search_cache_key = _cache_key(latitude, longitude, radius, category)
    cached_businesses = cache.get(search_cache_key)
    if cached_businesses is not None:
        logger.info('Business search served from cache for category %s.', category)
        return cached_businesses

    query = _build_overpass_query(
        latitude, longitude, radius, category_config['osm_tags']
    )
    endpoints = _configured_endpoints()
    response = None
    last_error = None
    for index, endpoint in enumerate(endpoints):
        try:
            response = _request_overpass(endpoint, query)
            if index:
                logger.info('Fallback Overpass request succeeded.')
            break
        except OpenStreetMapError as exc:
            last_error = exc
            label = 'primary' if index == 0 else 'fallback'
            logger.warning('Overpass %s failed: %s', label, exc)
            if not exc.retryable or index == len(endpoints) - 1:
                break
            logger.info('Trying configured fallback.')
    if response is None:
        if last_error and last_error.retryable and len(endpoints) > 1:
            logger.error('Both Overpass endpoints unavailable.')
        else:
            logger.error('Overpass request failed without fallback.')
        raise last_error or OpenStreetMapError('The Overpass API is unavailable.')

    try:
        payload = response.json()
    except ValueError as exc:
        raise OpenStreetMapError('The Overpass API returned invalid JSON.') from exc

    if not isinstance(payload, dict):
        raise OpenStreetMapError('The Overpass API returned an invalid response structure.')
    elements = payload.get('elements', [])
    if not isinstance(elements, list):
        raise OpenStreetMapError('The Overpass API response has invalid elements.')

    businesses = []
    seen = set()
    for element in elements:
        business = _normalize_element(element)
        if business is None:
            logger.warning('Skipping a malformed OpenStreetMap element.')
            continue
        key = (business['osm_type'], business['osm_id'])
        if key in seen:
            continue
        seen.add(key)
        business['category'] = category
        businesses.append(business)
    businesses = _add_distances_and_sort(
        _deduplicate_hotels(businesses),
        origin_latitude=latitude,
        origin_longitude=longitude,
    )
    cache.set(search_cache_key, businesses, CACHE_TIMEOUT_SECONDS)
    return businesses


def search_nearby_hotels(latitude, longitude, radius):
    """Backward-compatible Hotels & Resorts search wrapper."""
    return search_nearby_businesses(
        latitude=latitude,
        longitude=longitude,
        radius=radius,
        category='hotels_resorts',
    )
