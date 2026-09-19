from rest_framework import serializers

from .business_categories import BUSINESS_CATEGORIES
from .models import ProviderSettings
from .services.providers.search_depth import SEARCH_DEPTHS


class SearchCreateSerializer(serializers.Serializer):
    location_name = serializers.CharField(max_length=300)
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    radius_m = serializers.IntegerField(min_value=1, max_value=20_000)
    category = serializers.ChoiceField(choices=tuple(BUSINESS_CATEGORIES))
    providers = serializers.ListField(
        child=serializers.ChoiceField(choices=ProviderSettings.BUSINESS_PROVIDER_CHOICES),
        min_length=1, max_length=4,
    )
    search_depth = serializers.ChoiceField(choices=SEARCH_DEPTHS, default="standard")

    def validate(self, attrs):
        if "playwright" not in attrs["providers"]:
            attrs["search_depth"] = "standard"
        attrs["providers"] = list(dict.fromkeys(attrs["providers"]))
        return attrs


class BusinessIdsSerializer(serializers.Serializer):
    business_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=1, max_length=100
    )


class SearchBusinessIdsSerializer(BusinessIdsSerializer):
    search_id = serializers.IntegerField(min_value=1)


class ImportSerializer(SearchBusinessIdsSerializer):
    service_id = serializers.IntegerField(min_value=1)


class DecisionMakerSerializer(SearchBusinessIdsSerializer):
    providers = serializers.ListField(
        child=serializers.ChoiceField(choices=(
            ("official_website", "Official Website"),
            ("apollo", "Apollo"),
            ("zoominfo", "ZoomInfo"),
        )),
        allow_empty=False,
        max_length=3,
    )

    def validate_providers(self, value):
        return list(dict.fromkeys(value))


class ProviderSettingsUpdateSerializer(serializers.Serializer):
    business_providers = serializers.ListField(
        child=serializers.ChoiceField(choices=ProviderSettings.BUSINESS_PROVIDER_CHOICES),
        allow_empty=False,
    )
    people_providers = serializers.ListField(
        child=serializers.ChoiceField(choices=(
            ("official_website", "Official Website"),
            ("apollo", "Apollo"),
            ("zoominfo", "ZoomInfo"),
        )),
        allow_empty=True,
    )
    google_api_key = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    geoapify_api_key = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    apollo_api_key = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    zoominfo_api_key = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)

    def validate(self, attrs):
        attrs["business_providers"] = list(dict.fromkeys(attrs["business_providers"]))
        attrs["people_providers"] = list(dict.fromkeys(attrs["people_providers"]))
        return attrs
