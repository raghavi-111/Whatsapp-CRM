import math

import requests

from .geoapify_categories import get_geoapify_categories
from .openstreetmap import calculate_distance_km


GEOAPIFY_PLACES_URL = 'https://api.geoapify.com/v2/places'
REQUEST_TIMEOUT_SECONDS = 30
RESULT_LIMIT = 50


class GeoapifyError(Exception):
    """Raised when a Geoapify Places request or response fails."""


def _coordinates(feature, properties):
    geometry = feature.get('geometry') or {}
    coordinates = geometry.get('coordinates') or []
    if geometry.get('type') == 'Point' and len(coordinates) >= 2:
        return coordinates[1], coordinates[0]
    return properties.get('lat'), properties.get('lon')


def _distance(properties, origin_latitude, origin_longitude, latitude, longitude):
    try:
        distance_meters = float(properties.get('distance'))
        if math.isfinite(distance_meters) and distance_meters >= 0:
            return round(distance_meters / 1000, 2)
    except (TypeError, ValueError, OverflowError):
        pass
    return calculate_distance_km(
        origin_latitude, origin_longitude, latitude, longitude
    )


def _normalize_feature(feature, origin_latitude, origin_longitude, category):
    if not isinstance(feature, dict):
        return None
    properties = feature.get('properties') or {}
    if not isinstance(properties, dict):
        return None
    latitude, longitude = _coordinates(feature, properties)
    contact = properties.get('contact') or {}
    if not isinstance(contact, dict):
        contact = {}
    datasource = properties.get('datasource') or {}
    raw = datasource.get('raw') or {} if isinstance(datasource, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    place_id = properties.get('place_id')
    return {
        'id': place_id,
        'osm_type': None,
        'osm_id': None,
        'place_id': place_id,
        'name': properties.get('name'),
        'address': properties.get('formatted'),
        'latitude': latitude,
        'longitude': longitude,
        'distance_km': _distance(
            properties, origin_latitude, origin_longitude, latitude, longitude
        ),
        'phone': contact.get('phone') or properties.get('phone') or raw.get('phone'),
        'email': contact.get('email') or properties.get('email') or raw.get('email'),
        'website': properties.get('website') or raw.get('website'),
        'brand': properties.get('brand') or raw.get('brand'),
        'stars': properties.get('stars') or raw.get('stars'),
        'source': 'Geoapify',
        'category': category,
    }


def search_nearby_businesses(latitude, longitude, radius, category, api_key):
    """Search Geoapify Places once and normalize its GeoJSON features."""
    try:
        geoapify_categories = get_geoapify_categories(category)
    except ValueError as exc:
        raise GeoapifyError(str(exc)) from exc

    try:
        response = requests.get(
            GEOAPIFY_PLACES_URL,
            params={
                'categories': ','.join(geoapify_categories),
                'filter': f'circle:{longitude:g},{latitude:g},{radius:g}',
                'bias': f'proximity:{longitude:g},{latitude:g}',
                'limit': RESULT_LIMIT,
                'apiKey': api_key,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise GeoapifyError('The Geoapify request timed out.') from exc
    except requests.ConnectionError as exc:
        raise GeoapifyError('Could not connect to Geoapify.') from exc
    except requests.RequestException as exc:
        raise GeoapifyError('The Geoapify request failed.') from exc

    if response.status_code in {401, 403}:
        raise GeoapifyError('Geoapify denied access. Check the configured API key.')
    if response.status_code == 429:
        raise GeoapifyError('Geoapify quota or rate limit was reached.')
    if response.status_code >= 500:
        raise GeoapifyError('Geoapify is temporarily unavailable.')
    if response.status_code != 200:
        raise GeoapifyError('Geoapify returned an unexpected response.')

    try:
        payload = response.json()
    except ValueError as exc:
        raise GeoapifyError('Geoapify returned invalid JSON.') from exc
    if not isinstance(payload, dict) or not isinstance(payload.get('features'), list):
        raise GeoapifyError('Geoapify returned an invalid response structure.')

    businesses = [
        business
        for feature in payload['features']
        if (business := _normalize_feature(
            feature, latitude, longitude, category
        )) is not None
    ]
    return sorted(
        businesses,
        key=lambda business: (
            business['distance_km'] is None,
            business['distance_km'] if business['distance_km'] is not None else math.inf,
        ),
    )
