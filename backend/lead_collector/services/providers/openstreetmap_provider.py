from ..openstreetmap import search_nearby_businesses, search_nearby_hotels
from .base import HotelProvider


class OpenStreetMapProvider(HotelProvider):
    def search_nearby_businesses(
        self, latitude, longitude, radius, category='hotels_resorts',
    ):
        return search_nearby_businesses(latitude, longitude, radius, category)

    def search_nearby_hotels(self, latitude, longitude, radius):
        return search_nearby_hotels(latitude, longitude, radius)
