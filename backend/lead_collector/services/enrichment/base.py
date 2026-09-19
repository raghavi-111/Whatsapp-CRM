from abc import ABC, abstractmethod


class HotelEnrichmentProvider(ABC):
    """Interface for replaceable hotel enrichment providers."""

    @abstractmethod
    def enrich(self, hotel):
        raise NotImplementedError


class EnrichmentError(Exception):
    """Raised when an enrichment provider cannot safely complete its work."""
