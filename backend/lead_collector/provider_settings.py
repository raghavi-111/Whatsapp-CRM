from django.conf import settings

from .models import ProviderSettings


def get_provider_settings(organization=None):
    if organization is None:
        raise ValueError("Organization is required for Lead Collector provider settings.")
    instance, _ = ProviderSettings.objects.get_or_create(organization=organization)
    return instance


def get_google_api_key(provider_settings):
    return provider_settings.get_google_api_key() or getattr(settings, "GOOGLE_MAPS_API_KEY", "")


def get_geoapify_api_key(provider_settings):
    return provider_settings.get_geoapify_api_key() or getattr(settings, "GEOAPIFY_API_KEY", "")


def get_apollo_api_key(provider_settings):
    return provider_settings.get_apollo_api_key() or getattr(settings, "APOLLO_API_KEY", "")


def get_zoominfo_api_key(provider_settings):
    return provider_settings.get_zoominfo_api_key() or getattr(settings, "ZOOMINFO_API_KEY", "")


def get_business_providers(provider_settings):
    valid = {choice[0] for choice in ProviderSettings.BUSINESS_PROVIDER_CHOICES}
    selected = provider_settings.business_providers or [ProviderSettings.OPENSTREETMAP]
    return list(dict.fromkeys(item for item in selected if item in valid))


def get_people_providers(provider_settings):
    selected = provider_settings.people_providers or []
    return list(dict.fromkeys(
        item for item in selected if item in {"official_website", "apollo", "zoominfo"}
    ))


def public_provider_settings(provider_settings):
    return {
        "business_providers": get_business_providers(provider_settings),
        "google_configured": bool(get_google_api_key(provider_settings)),
        "geoapify_configured": bool(get_geoapify_api_key(provider_settings)),
        "people_providers": get_people_providers(provider_settings),
        "apollo_configured": bool(get_apollo_api_key(provider_settings)),
        "zoominfo_configured": bool(get_zoominfo_api_key(provider_settings)),
        "providers": {
            "openstreetmap": {"configured": True, "requires_key": False},
            "playwright": {"configured": True, "requires_key": False},
            "geoapify": {"configured": bool(get_geoapify_api_key(provider_settings)), "requires_key": True},
            "google": {"configured": bool(get_google_api_key(provider_settings)), "requires_key": True},
            "official_website": {"configured": True, "requires_key": False},
            "apollo": {"configured": bool(get_apollo_api_key(provider_settings)), "requires_key": True},
            "zoominfo": {"configured": bool(get_zoominfo_api_key(provider_settings)), "requires_key": True},
        },
    }
