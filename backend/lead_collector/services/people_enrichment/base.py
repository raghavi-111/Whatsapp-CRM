from abc import ABC, abstractmethod


class PeopleEnrichmentProvider(ABC):
    @abstractmethod
    def search_decision_makers(self, business, category='hotels_resorts'):
        raise NotImplementedError


class PeopleEnrichmentError(Exception):
    """Base error for professional-contact providers."""


class PeopleEnrichmentConfigurationError(PeopleEnrichmentError):
    """Raised when a provider is not configured."""
