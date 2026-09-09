from abc import ABC, abstractmethod


class HotelProvider(ABC):
    def search_nearby_businesses(
        self, latitude, longitude, radius, category='hotels_resorts',
    ):
        if category != 'hotels_resorts':
            raise UnsupportedBusinessCategoryError(
                'The selected business category is not supported by this provider.'
            )
        return self.search_nearby_hotels(latitude, longitude, radius)

    @abstractmethod
    def search_nearby_hotels(self, latitude, longitude, radius):
        raise NotImplementedError


class HotelProviderConfigurationError(Exception):
    """Raised when a selected provider lacks required configuration."""


class UnsupportedBusinessCategoryError(Exception):
    """Raised when the selected provider cannot search a valid category."""
