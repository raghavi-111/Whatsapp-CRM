"""Prioritized Apollo decision-maker roles by internal business category."""


ROLE_PROFILES = {
    'hotels_resorts': {
        'General Management': ('General Manager', 'Hotel General Manager', 'Hotel Manager'),
        'Marketing': ('Marketing Manager', 'Director of Marketing', 'Director of Sales and Marketing', 'Head of Marketing'),
        'IT': ('IT Manager', 'Information Technology Manager', 'Director of IT', 'Head of IT'),
    },
    'cafes': {
        'Leadership': ('Owner', 'Founder', 'General Manager'),
        'Operations': ('Operations Manager', 'Area Manager'),
        'Marketing': ('Marketing Manager',),
    },
    'restaurants': {
        'Leadership': ('Owner', 'Founder', 'General Manager', 'Restaurant Manager'),
        'Operations': ('Operations Manager', 'Area Manager'),
        'Marketing': ('Marketing Manager', 'Head of Marketing'),
    },
    'shopping_malls': {
        'Leadership': ('General Manager', 'Mall Manager', 'Centre Manager'),
        'Operations': ('Operations Manager', 'Facility Manager'),
        'Marketing': ('Marketing Manager', 'Head of Marketing'),
        'IT': ('IT Manager',),
    },
    'hospitals': {
        'Leadership': ('Hospital Administrator', 'Administrator', 'Director', 'Managing Director'),
        'Marketing': ('Marketing Manager', 'Head of Marketing'),
        'IT': ('IT Manager', 'IT Director', 'Head of IT', 'CIO'),
    },
    'coworking_spaces': {
        'Leadership': ('Founder', 'General Manager', 'Centre Manager'),
        'Operations': ('Operations Manager', 'Community Manager'),
        'Marketing': ('Marketing Manager',),
        'IT': ('IT Manager',),
    },
    'salons_spas': {
        'Leadership': ('Owner', 'Founder', 'General Manager'),
        'Operations': ('Operations Manager', 'Salon Manager', 'Spa Manager'),
        'Marketing': ('Marketing Manager',),
    },
    'gyms_fitness': {
        'Leadership': ('Owner', 'Founder', 'General Manager', 'Club Manager'),
        'Operations': ('Operations Manager',),
        'Marketing': ('Marketing Manager',),
    },
    'universities_colleges': {
        'Leadership': ('Director', 'Dean', 'Registrar', 'Principal'),
        'Marketing': ('Marketing Manager', 'Head of Marketing', 'Admissions Director'),
        'IT': ('IT Director', 'IT Manager', 'Head of IT', 'CIO'),
    },
    'schools': {
        'Leadership': ('Principal', 'School Principal', 'Director', 'Managing Director'),
        'Administration': ('Administrator', 'School Administrator', 'Operations Manager'),
        'IT': ('IT Manager', 'Head of IT', 'IT Administrator'),
    },
    'airports': {
        'Leadership': ('Airport Director', 'General Manager'),
        'Operations': ('Operations Manager', 'Airport Operations Manager'),
        'IT': ('IT Manager', 'IT Director', 'CIO'),
        'Marketing': ('Marketing Manager',),
    },
    'retail': {
        'Leadership': ('Store Manager', 'General Manager', 'Regional Manager', 'Director'),
        'Operations': ('Operations Manager',),
        'Marketing': ('Marketing Manager',),
        'IT': ('IT Manager',),
    },
    'event_venues': {
        'Leadership': ('General Manager', 'Venue Manager', 'Director'),
        'Operations': ('Operations Manager', 'Event Manager'),
        'Marketing': ('Marketing Manager',),
    },
    'banks': {
        'Leadership': ('Branch Manager', 'Regional Manager', 'General Manager'),
        'Operations': ('Operations Manager',),
        'IT': ('IT Manager', 'IT Director'),
        'Marketing': ('Marketing Manager',),
    },
    'petrol_stations': {
        'Leadership': ('Owner', 'Dealer', 'Manager', 'Area Manager'),
        'Operations': ('Operations Manager',),
    },
    'pharmacies': {
        'Leadership': ('Owner', 'General Manager', 'Store Manager'),
        'Operations': ('Operations Manager',),
    },
    'hostels': {
        'Leadership': ('Owner', 'General Manager', 'Hostel Manager'),
        'Operations': ('Operations Manager',),
        'Marketing': ('Marketing Manager',),
    },
}

PRIMARY_ROLE_PROFILE = {
    'IT Leadership': (
        'IT Director', 'Director of IT', 'Director, Information Technology',
        'Head of IT', 'Head of Information Technology', 'VP of IT',
        'VP Information Technology',
    ),
    'IT Management': (
        'IT Manager', 'Information Technology Manager', 'Infrastructure Manager',
        'IT Infrastructure Manager', 'Technology Manager',
    ),
    'General Management': ('General Manager', 'Managing Director', 'Business General Manager'),
    'Executive Technology': ('CIO', 'Chief Information Officer', 'CTO', 'Chief Technology Officer'),
    'Operations Leadership': ('Director of Operations', 'Operations Director', 'Head of Operations'),
}


def get_role_profile(category):
    try:
        category_profile = ROLE_PROFILES[category]
    except (KeyError, TypeError) as exc:
        raise ValueError(f'Unknown business category: {category!r}.') from exc
    return {**PRIMARY_ROLE_PROFILE, **category_profile}


def get_search_titles(category):
    return [title for titles in get_role_profile(category).values() for title in titles]
