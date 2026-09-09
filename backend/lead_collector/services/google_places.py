import logging

import requests
from django.conf import settings


logger = logging.getLogger(__name__)

NEARBY_SEARCH_URL = 'https://places.googleapis.com/v1/places:searchNearby'
FIELD_MASK = ','.join([
    'places.id',
    'places.displayName',
    'places.formattedAddress',
    'places.location',
    'places.googleMapsUri',
])
REQUEST_TIMEOUT_SECONDS = 10


class GooglePlacesError(Exception):
    """Raised when Google Places cannot complete a request safely."""


def _message_for_status(status_code):
    messages = {
        400: 'Google Places rejected the request as invalid.',
        401: 'Google Places authentication failed.',
        403: 'Google Places denied access. Check that Places API (New) is enabled and the key restrictions are correct.',
        429: 'Google Places quota has been exceeded.',
    }
    return messages.get(
        status_code,
        f'Google Places returned an unexpected HTTP {status_code} response.',
    )


def _normalize_place(place):
    display_name = place.get('displayName') or {}
    location = place.get('location') or {}

    return {
        'place_id': place.get('id'),
        'name': display_name.get('text'),
        'address': place.get('formattedAddress'),
        'latitude': location.get('latitude'),
        'longitude': location.get('longitude'),
        'google_maps_url': place.get('googleMapsUri'),
    }


def search_nearby_hotels(latitude, longitude, radius, api_key=None):
    """Return normalized hotels from one Places API Nearby Search request."""
    api_key = api_key or settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        raise GooglePlacesError('GOOGLE_MAPS_API_KEY is not configured.')

    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': FIELD_MASK,
    }
    payload = {
        'includedTypes': ['hotel'],
        'maxResultCount': 20,
        'locationRestriction': {
            'circle': {
                'center': {
                    'latitude': latitude,
                    'longitude': longitude,
                },
                'radius': radius,
            },
        },
    }

    try:
        response = requests.post(
            NEARBY_SEARCH_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        logger.error('Google Places request timed out.')
        raise GooglePlacesError('Google Places request timed out.') from exc
    except requests.RequestException as exc:
        logger.error('Google Places network request failed.')
        raise GooglePlacesError('Could not connect to Google Places.') from exc

    if response.status_code != 200:
        message = _message_for_status(response.status_code)
        logger.error('Google Places request failed with HTTP status %s.', response.status_code)
        raise GooglePlacesError(message)

    try:
        data = response.json()
    except ValueError as exc:
        logger.error('Google Places returned invalid JSON.')
        raise GooglePlacesError('Google Places returned an invalid JSON response.') from exc

    places = data.get('places', [])
    if not isinstance(places, list):
        logger.error('Google Places response contained an invalid places value.')
        raise GooglePlacesError('Google Places returned an invalid response structure.')

    return [_normalize_place(place) for place in places]
