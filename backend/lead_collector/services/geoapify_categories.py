"""Trusted mappings from internal business IDs to Geoapify Places categories."""


GEOAPIFY_CATEGORY_MAPPINGS = {
    'hotels_resorts': ('accommodation.hotel', 'beach.beach_resort'),
    'cafes': ('catering.cafe',),
    'restaurants': ('catering.restaurant',),
    'shopping_malls': ('commercial.shopping_mall',),
    'hospitals': ('healthcare.hospital',),
    'coworking_spaces': ('office.coworking',),
    'salons_spas': ('service.beauty',),
    'gyms_fitness': ('sport.fitness',),
    'universities_colleges': ('education.university', 'education.college'),
    'schools': ('education.school',),
    'airports': ('airport',),
    'retail': ('commercial',),
    'event_venues': ('activity.events_venue',),
    'banks': ('service.financial.bank',),
    'petrol_stations': ('service.vehicle.fuel',),
    'pharmacies': ('healthcare.pharmacy',),
    'hostels': ('accommodation.hostel',),
}


def get_geoapify_categories(category_id):
    categories = GEOAPIFY_CATEGORY_MAPPINGS.get(category_id)
    if not categories:
        raise ValueError(
            'The selected business category is not supported by Geoapify in this version.'
        )
    return categories
