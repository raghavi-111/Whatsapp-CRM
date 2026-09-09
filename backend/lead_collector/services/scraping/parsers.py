import re
from urllib.parse import parse_qs, unquote, urlparse


COORDINATE_PATTERNS = (
    re.compile(r'/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)'),
    re.compile(r'!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)'),
)


def _number(value, cast=float):
    if value in (None, ''):
        return None
    match = re.search(r'[\d,.]+', str(value))
    if not match:
        return None
    try:
        return cast(match.group().replace(',', ''))
    except ValueError:
        return None


def _review_count(value):
    text = str(value or '')
    match = re.search(r'\(([\d,]+)\)|([\d,]+)\s+reviews?', text, re.IGNORECASE)
    return int((match.group(1) or match.group(2)).replace(',', '')) if match else None


def _detail(value):
    if not value:
        return None
    return re.sub(r'^(address|phone|hours)\s*:\s*', '', str(value), flags=re.IGNORECASE).strip() or None


def coordinates_from_url(url):
    for pattern in COORDINATE_PATTERNS:
        match = pattern.search(url or '')
        if match:
            latitude, longitude = float(match.group(1)), float(match.group(2))
            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                return latitude, longitude
    return None, None


def place_identifier(url):
    query = parse_qs(urlparse(url).query) if url else {}
    query_identifier = (query.get('query_place_id') or [None])[0]
    if query_identifier:
        return query_identifier
    match = re.search(r'!19s([^!?]+)', url or '')
    return unquote(match.group(1)) if match else None


def normalize_listing(raw, category):
    raw = raw if isinstance(raw, dict) else {}
    name = str(raw.get('name') or '').strip()
    if not name:
        return None
    maps_url = raw.get('maps_url') or raw.get('google_maps_url')
    latitude, longitude = coordinates_from_url(maps_url)
    identifier = place_identifier(maps_url)
    return {
        'id': identifier, 'place_id': identifier, 'name': name,
        'category': raw.get('category') or category, 'address': _detail(raw.get('address')),
        'phone': _detail(raw.get('phone')), 'website': raw.get('website') or None,
        'rating': _number(raw.get('rating')), 'review_count': _review_count(raw.get('review_count')),
        'maps_url': maps_url or None, 'google_maps_url': maps_url or None,
        'latitude': raw.get('latitude') if raw.get('latitude') is not None else latitude,
        'longitude': raw.get('longitude') if raw.get('longitude') is not None else longitude,
        'opening_hours': _detail(raw.get('opening_hours')), 'email': None,
        'brand': None, 'stars': None, 'source': 'Browser Search',
    }


def listing_identity(listing):
    place_id = (
        listing.get('place_id') or listing.get('id')
        or place_identifier(listing.get('maps_url') or listing.get('google_maps_url'))
    )
    if place_id:
        return ('place_id', str(place_id))
    maps_url = listing.get('maps_url') or listing.get('google_maps_url')
    if maps_url:
        return ('maps_url', str(maps_url).split('#', 1)[0])
    name = ' '.join(str(listing.get('name') or '').casefold().split())
    address = ' '.join(str(listing.get('address') or '').casefold().split())
    if address:
        return ('name_address', name, address)
    latitude, longitude = listing.get('latitude'), listing.get('longitude')
    return ('name_coordinates', name, latitude, longitude)


def listing_identity_keys(listing):
    """Return strong equivalent identities without merging same-name branches."""
    keys = {listing_identity(listing)}
    name = ' '.join(str(listing.get('name') or '').casefold().split())
    address = ' '.join(str(listing.get('address') or '').casefold().split())
    if name and address:
        keys.add(('name_address', name, address))
    latitude, longitude = listing.get('latitude'), listing.get('longitude')
    if name and latitude is not None and longitude is not None:
        keys.add(('name_coordinates', name, round(float(latitude), 6), round(float(longitude), 6)))
    return keys


def deduplicate_listings(listings):
    unique, keys = [], set()
    for listing in listings:
        candidate_keys = listing_identity_keys(listing)
        if keys.isdisjoint(candidate_keys):
            keys.update(candidate_keys)
            unique.append(listing)
    return unique
