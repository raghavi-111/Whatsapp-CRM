"""Trusted OpenStreetMap mappings for normalized business categories."""


BUSINESS_CATEGORIES = {
    'hotels_resorts': {
        'id': 'hotels_resorts',
        'display_name': 'Hotels & Resorts',
        'osm_tags': [
            {'key': 'tourism', 'value': 'hotel'},
            {'key': 'tourism', 'value': 'resort'},
        ],
    },
    'cafes': {
        'id': 'cafes',
        'display_name': 'Cafés & Coffee Chains',
        'osm_tags': [{'key': 'amenity', 'value': 'cafe'}],
    },
    'restaurants': {
        'id': 'restaurants',
        'display_name': 'Restaurants',
        'osm_tags': [{'key': 'amenity', 'value': 'restaurant'}],
    },
    'shopping_malls': {
        'id': 'shopping_malls',
        'display_name': 'Shopping Malls',
        'osm_tags': [{'key': 'shop', 'value': 'mall'}],
    },
    'hospitals': {
        'id': 'hospitals',
        'display_name': 'Hospitals',
        'osm_tags': [{'key': 'amenity', 'value': 'hospital'}],
    },
    'coworking_spaces': {
        'id': 'coworking_spaces',
        'display_name': 'Coworking Spaces',
        'osm_tags': [{'key': 'office', 'value': 'coworking'}],
    },
    'salons_spas': {
        'id': 'salons_spas',
        'display_name': 'Salons & Spas',
        'osm_tags': [
            {'key': 'shop', 'value': 'hairdresser'},
            {'key': 'shop', 'value': 'beauty'},
        ],
    },
    'gyms_fitness': {
        'id': 'gyms_fitness',
        'display_name': 'Gyms & Fitness Centers',
        'osm_tags': [{'key': 'leisure', 'value': 'fitness_centre'}],
    },
    'universities_colleges': {
        'id': 'universities_colleges',
        'display_name': 'Universities & Colleges',
        'osm_tags': [
            {'key': 'amenity', 'value': 'university'},
            {'key': 'amenity', 'value': 'college'},
        ],
    },
    'schools': {
        'id': 'schools',
        'display_name': 'Schools',
        'osm_tags': [{'key': 'amenity', 'value': 'school'}],
    },
    'airports': {
        'id': 'airports',
        'display_name': 'Airports',
        'osm_tags': [{'key': 'aeroway', 'value': 'aerodrome'}],
    },
    'retail': {
        'id': 'retail',
        'display_name': 'Retail Stores / Retail Chains',
        'osm_tags': [{'key': 'shop', 'value': None, 'match': 'exists'}],
    },
    'event_venues': {
        'id': 'event_venues',
        'display_name': 'Event Venues',
        'osm_tags': [{'key': 'amenity', 'value': 'events_venue'}],
    },
    'banks': {
        'id': 'banks',
        'display_name': 'Banks',
        'osm_tags': [{'key': 'amenity', 'value': 'bank'}],
    },
    'petrol_stations': {
        'id': 'petrol_stations',
        'display_name': 'Petrol Stations',
        'osm_tags': [{'key': 'amenity', 'value': 'fuel'}],
    },
    'pharmacies': {
        'id': 'pharmacies',
        'display_name': 'Pharmacies',
        'osm_tags': [{'key': 'amenity', 'value': 'pharmacy'}],
    },
    'hostels': {
        'id': 'hostels',
        'display_name': 'Hostels',
        'osm_tags': [{'key': 'tourism', 'value': 'hostel'}],
    },
}


def get_business_category(category_id):
    """Return a trusted category definition or reject an unknown ID."""
    try:
        return BUSINESS_CATEGORIES[category_id]
    except (KeyError, TypeError) as exc:
        raise ValueError(f'Unknown business category: {category_id!r}.') from exc


def get_business_categories():
    """Return all category definitions in their stable display order."""
    return list(BUSINESS_CATEGORIES.values())
