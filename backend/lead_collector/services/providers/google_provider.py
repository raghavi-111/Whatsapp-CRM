from ..google_places import search_nearby_hotels
from ..openstreetmap import calculate_distance_km
from .base import (
    HotelProvider,
    HotelProviderConfigurationError,
    UnsupportedBusinessCategoryError,
)


class GooglePlacesProvider(HotelProvider):
    def __init__(self, api_key):
        if not api_key:
            raise HotelProviderConfigurationError(
                'Google Places is selected but no API key is configured.'
            )
        self.api_key = api_key

    def search_nearby_hotels(self, latitude, longitude, radius):
        places = search_nearby_hotels(latitude, longitude, radius, api_key=self.api_key)
        hotels = []
        for place in places:
            hotel = {
                'id': place.get('place_id'),
                'osm_type': None,
                'osm_id': None,
                'place_id': place.get('place_id'),
                'name': place.get('name'),
                'address': place.get('address'),
                'latitude': place.get('latitude'),
                'longitude': place.get('longitude'),
                'distance_km': calculate_distance_km(
                    latitude, longitude, place.get('latitude'), place.get('longitude')
                ),
                'phone': None,
                'email': None,
                'website': None,
                'google_maps_url': place.get('google_maps_url'),
                'brand': None,
                'stars': None,
                'source': 'Google Places',
            }
            hotels.append(hotel)
        return sorted(
            hotels,
            key=lambda hotel: (
                hotel['distance_km'] is None,
                hotel['distance_km'] if hotel['distance_km'] is not None else float('inf'),
            ),
        )

    def search_nearby_businesses(
        self, latitude, longitude, radius, category='hotels_resorts',
    ):
        if category != 'hotels_resorts':
            raise UnsupportedBusinessCategoryError(
                'The selected business category is not yet supported by Google Places '
                'in this version.'
            )
        return self.search_nearby_hotels(latitude, longitude, radius)
