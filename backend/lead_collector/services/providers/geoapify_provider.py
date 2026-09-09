from ..geoapify import search_nearby_businesses
from ..geoapify_categories import get_geoapify_categories
from .base import (
    HotelProvider,
    HotelProviderConfigurationError,
    UnsupportedBusinessCategoryError,
)


class GeoapifyProvider(HotelProvider):
    def __init__(self, api_key):
        if not api_key:
            raise HotelProviderConfigurationError(
                'Geoapify is selected but no API key is configured.'
            )
        self.api_key = api_key

    def search_nearby_businesses(
        self, latitude, longitude, radius, category='hotels_resorts',
    ):
        try:
            get_geoapify_categories(category)
        except ValueError as exc:
            raise UnsupportedBusinessCategoryError(str(exc)) from exc
        return search_nearby_businesses(
            latitude, longitude, radius, category, api_key=self.api_key
        )

    def search_nearby_hotels(self, latitude, longitude, radius):
        return self.search_nearby_businesses(
            latitude, longitude, radius, category='hotels_resorts'
        )
