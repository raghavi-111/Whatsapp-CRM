import csv
import logging
import re
from io import StringIO

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.permissions import can_manage_settings, get_current_membership, get_current_organization

from .business_categories import get_business_categories
from .models import DiscoveredBusiness, DiscoverySearch
from .provider_settings import (
    get_apollo_api_key, get_geoapify_api_key, get_google_api_key,
    get_provider_settings, get_zoominfo_api_key, public_provider_settings,
)
from .serializers import BusinessIdsSerializer, DecisionMakerSerializer, ImportSerializer, ProviderSettingsUpdateSerializer, SearchBusinessIdsSerializer, SearchCreateSerializer
from .services.crm_import import import_businesses, preview_import
from .services.whatsapp_contact_import import import_whatsapp_contacts, preview_whatsapp_contacts
from .services.export.excel import build_hotel_workbook, sanitize_spreadsheet_value
from .services.export.enrichment import prepare_hotels_for_export
from .services.geocoding.nominatim import NominatimError, search_locations
from .services.identity import business_identity, normalized_domain, normalized_phone, provider_place_id
from .services.people_enrichment.base import PeopleEnrichmentError
from .services.people_enrichment.orchestrator import search_decision_makers_multi_provider
from .services.providers.orchestrator import search_businesses_multi_provider


logger = logging.getLogger(__name__)


def export_filename(location, extension, exported_at=None):
    slug = re.sub(r"[^a-z0-9]+", "-", (location or "").casefold()).strip("-")[:80]
    date = (exported_at or timezone.now()).date().isoformat()
    return f"business-leads-{slug + '-' if slug else ''}{date}.{extension}"


def export_context(search):
    return {
        "id": search.id, "location": search.location_name,
        "latitude": search.latitude, "longitude": search.longitude,
        "radius": search.radius_m, "category": search.category,
        "provider": " + ".join(search.providers),
        "search_depth": search.search_depth, "searched_at": search.created_at.isoformat(),
    }


def prepare_persisted_businesses(businesses):
    """Run bounded Official Website preparation and persist its safe merge."""
    prepared = prepare_hotels_for_export([business.payload for business in businesses])
    for business, payload in zip(businesses, prepared):
        if payload == business.payload:
            continue
        business.payload = payload
        business.phone_normalized = normalized_phone(payload.get("phone"))
        business.website_domain = normalized_domain(payload.get("website"))
        business.save(update_fields=["payload", "phone_normalized", "website_domain"])
    return prepared


def csv_export_values(item):
    join = lambda values: "; ".join(str(value) for value in values if value)
    emails = item.get("business_emails") or []
    phones = item.get("business_phones") or []
    whatsapp = [contact for contact in item.get("whatsapp_contacts") or [] if contact.get("status") == "CONFIRMED_PUBLIC"]
    social = item.get("social_profiles") or {}
    social_sources = item.get("social_profile_sources") or {}
    people = item.get("decision_makers") or []
    return [
        item.get(key) for key in (
            "name", "address", "distance_km", "phone", "email", "website", "brand",
            "rating", "review_count", "latitude", "longitude", "source", "enrichment_status",
        )
    ] + [
        join(f'{row.get("email")} [{row.get("type") or "other"}]' for row in emails),
        join(row.get("source_url") for row in emails),
        join(f'{row.get("phone")} [{row.get("type") or "general"}]' for row in phones),
        join(row.get("source_url") for row in phones),
        join(row.get("normalized") or row.get("number") for row in whatsapp),
        "CONFIRMED_PUBLIC" if whatsapp else "UNKNOWN",
        join(row.get("source_url") for row in whatsapp),
        social.get("linkedin"), social_sources.get("linkedin"),
        social.get("facebook"), social_sources.get("facebook"),
        social.get("instagram"), social_sources.get("instagram"),
        join(f'{row.get("name") or "Team"} - {row.get("title") or row.get("role_group") or ""}' for row in people),
        join(row.get("source_url") for row in people),
    ]


def organization_or_response(request):
    organization = get_current_organization(request.user)
    if organization is None:
        return None, Response({"detail": "No active organization found."}, status=404)
    return organization, None


def serialized_business(business):
    # Provider payloads may contain their own string `id` (for example a
    # Google place ID). CRM actions must always receive persisted record IDs.
    return {**business.payload, "id": business.id, "search_id": business.search_id}


def scoped_search_businesses(organization, values):
    search = DiscoverySearch.objects.filter(
        organization=organization, id=values["search_id"]
    ).first()
    if search is None:
        return None, []
    businesses = list(DiscoveredBusiness.objects.filter(
        organization=organization, search=search, id__in=values["business_ids"]
    ))
    by_id = {business.id: business for business in businesses}
    return search, [by_id[item_id] for item_id in values["business_ids"] if item_id in by_id]


class LocationSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if get_current_organization(request.user) is None:
            return Response({"detail": "No active organization found."}, status=404)
        query = request.query_params.get("q", "").strip()
        if len(query) < 3:
            return Response({"detail": "Enter at least three characters."}, status=400)
        try:
            return Response({"results": search_locations(query)})
        except NominatimError as error:
            return Response({"detail": str(error)}, status=502)


class CategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if get_current_organization(request.user) is None:
            return Response({"detail": "No active organization found."}, status=404)
        return Response({"categories": [
            {"id": item["id"], "name": item["display_name"]}
            for item in get_business_categories()
        ]})


class ProviderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = organization_or_response(request)
        if error: return error
        provider_settings = get_provider_settings(organization)
        return Response(public_provider_settings(provider_settings))

    def patch(self, request):
        membership = get_current_membership(request.user)
        if not can_manage_settings(membership):
            return Response({"detail": "Only owners and admins can manage Lead Collector settings."}, status=403)
        serializer = ProviderSettingsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider_settings = get_provider_settings(membership.organization)
        values = serializer.validated_data

        # Empty secret inputs mean "keep the saved value" so credentials never
        # need to be returned to or retained by the browser after submission.
        secret_fields = {
            "google_api_key": provider_settings.set_google_api_key,
            "geoapify_api_key": provider_settings.set_geoapify_api_key,
            "apollo_api_key": provider_settings.set_apollo_api_key,
            "zoominfo_api_key": provider_settings.set_zoominfo_api_key,
        }
        for field, setter in secret_fields.items():
            if values.get(field):
                setter(values[field])
        required_credentials = {
            "google": (get_google_api_key, "Google Places"),
            "geoapify": (get_geoapify_api_key, "Geoapify"),
            "apollo": (get_apollo_api_key, "Apollo"),
            "zoominfo": (get_zoominfo_api_key, "ZoomInfo"),
        }
        selected = set(values["business_providers"] + values["people_providers"])
        missing = [label for provider, (getter, label) in required_credentials.items()
                   if provider in selected and not getter(provider_settings)]
        if missing:
            return Response(
                {"detail": f"Add credentials before enabling: {', '.join(missing)}."},
                status=400,
            )
        provider_settings.business_providers = values["business_providers"]
        provider_settings.people_providers = values["people_providers"]
        provider_settings.apollo_enabled = "apollo" in values["people_providers"]
        provider_settings.save()
        return Response(public_provider_settings(provider_settings))


class SearchListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization, error = organization_or_response(request)
        if error: return error
        searches = DiscoverySearch.objects.filter(organization=organization)[:25]
        return Response({"results": [self._search_data(item) for item in searches]})

    def post(self, request):
        organization, error = organization_or_response(request)
        if error: return error
        serializer = SearchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data
        provider_settings = get_provider_settings(organization)
        enabled = set(provider_settings.business_providers)
        if any(provider not in enabled for provider in params["providers"]):
            return Response({"detail": "One or more providers are not enabled."}, status=400)
        search = DiscoverySearch.objects.create(
            organization=organization, created_by=request.user,
            status=DiscoverySearch.STATUS_RUNNING, **params,
        )
        try:
            result = search_businesses_multi_provider(
                latitude=search.latitude, longitude=search.longitude,
                radius=search.radius_m, category=search.category,
                providers=search.providers, provider_settings=provider_settings,
                search_depth=search.search_depth,
            )
            for payload in result["hotels"]:
                identity = business_identity(payload)
                if not identity: continue
                DiscoveredBusiness.objects.update_or_create(
                    search=search, identity_key=identity,
                    defaults={
                        "organization": organization,
                        "name": payload.get("name") or "Unnamed business",
                        "phone_normalized": normalized_phone(payload.get("phone")),
                        "website_domain": normalized_domain(payload.get("website")),
                        "provider_place_id": provider_place_id(payload),
                        "payload": payload,
                    },
                )
            search.status = DiscoverySearch.STATUS_COMPLETE
            search.diagnostics = {
                "provider_results": result.get("provider_results", {}),
                "raw_result_count": result.get("raw_result_count", 0),
                "deduplicated_count": result.get("deduplicated_count", 0),
            }
            search.save(update_fields=["status", "diagnostics", "updated_at"])
        except Exception:
            logger.exception(
                "Lead Collector search failed (search_id=%s, providers=%s, depth=%s)",
                search.id, search.providers, search.search_depth,
            )
            search.status = DiscoverySearch.STATUS_FAILED
            search.error = "Business discovery could not be completed."
            search.save(update_fields=["status", "error", "updated_at"])
            return Response(self._search_data(search), status=502)
        return Response(self._search_data(search, include_results=True), status=201)

    @staticmethod
    def _search_data(search, include_results=False):
        data = {
            "id": search.id, "location_name": search.location_name,
            "latitude": search.latitude, "longitude": search.longitude,
            "radius_m": search.radius_m, "category": search.category,
            "providers": search.providers, "search_depth": search.search_depth,
            "status": search.status, "diagnostics": search.diagnostics,
            "error": search.error, "created_at": search.created_at,
        }
        if include_results:
            data["businesses"] = [serialized_business(item) for item in search.businesses.all()]
        return data


class SearchDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, search_id):
        organization, error = organization_or_response(request)
        if error: return error
        search = DiscoverySearch.objects.filter(organization=organization, id=search_id).first()
        if not search: return Response({"detail": "Search not found."}, status=404)
        return Response(SearchListCreateView._search_data(search, include_results=True))


class EnrichBusinessesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error = organization_or_response(request)
        if error: return error
        serializer = SearchBusinessIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        search, businesses = scoped_search_businesses(organization, serializer.validated_data)
        if search is None:
            return Response({"detail": "Search not found."}, status=404)
        original = [dict(business.payload) for business in businesses]
        prepared = prepare_persisted_businesses(businesses)
        outcomes = []
        for business, before, after in zip(businesses, original, prepared):
            if not before.get("website"):
                outcome = "skipped_no_website"
            elif before.get("enrichment_status") and all(isinstance(before.get(field), expected) for field, expected in (
                ("business_emails", list), ("business_phones", list),
                ("social_profiles", dict), ("decision_makers", list),
            )):
                outcome = "already_enriched"
            elif after.get("enrichment_status") == "ERROR":
                outcome = "failed"
            else:
                outcome = "enriched"
            outcomes.append({"business_id": business.id, "status": outcome})
        return Response({"businesses": [serialized_business(item) for item in businesses], "outcomes": outcomes})


class DecisionMakersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error = organization_or_response(request)
        if error: return error
        serializer = DecisionMakerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider_settings = get_provider_settings(organization)
        providers = serializer.validated_data["providers"]
        search, businesses = scoped_search_businesses(organization, serializer.validated_data)
        if search is None:
            return Response({"detail": "Search not found."}, status=404)
        results = []
        for business in businesses:
            try:
                enrichment = search_decision_makers_multi_provider(
                    business=business.payload,
                    category=business.search.category,
                    providers=providers,
                    provider_settings=provider_settings,
                )
            except PeopleEnrichmentError:
                enrichment = {"contacts": [], "status": "ERROR"}
            except Exception:
                logger.error("Unexpected decision-maker enrichment failure for business %s.", business.id)
                enrichment = {"contacts": [], "status": "ERROR"}
            contacts = enrichment.get("contacts") or []
            business.payload = {
                **business.payload,
                "decision_makers": contacts,
                "manager_contacts": contacts,
                "decision_maker_status": enrichment.get("status"),
                "decision_maker_provider_results": enrichment.get("provider_results", {}),
            }
            business.save(update_fields=["payload"])
            results.append(serialized_business(business))
        return Response({"businesses": results})


class ExportView(APIView):
    permission_classes = [IsAuthenticated]
    export_format = "csv"

    def post(self, request):
        organization, error = organization_or_response(request)
        if error: return error
        serializer = BusinessIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_ids = serializer.validated_data["business_ids"]
        scoped = DiscoveredBusiness.objects.filter(organization=organization, id__in=requested_ids)
        requested_search_id = (request.data.get("context") or {}).get("id")
        search = DiscoverySearch.objects.filter(
            organization=organization, id=requested_search_id
        ).first() if requested_search_id else None
        if search is None:
            first = scoped.select_related("search").first()
            search = first.search if first else None
        if search is None:
            return Response({"detail": "No exportable businesses were found for this search."}, status=400)
        by_id = {item.id: item for item in scoped.filter(search=search)}
        businesses = [by_id[item_id] for item_id in requested_ids if item_id in by_id]
        if not businesses:
            return Response({"detail": "No exportable businesses were found for this search."}, status=400)
        payloads = prepare_persisted_businesses(businesses)
        context = export_context(search)
        if self.export_format == "excel":
            content, exported_at = build_hotel_workbook(payloads, context)
            response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f'attachment; filename="{export_filename(search.location_name, "xlsx", exported_at)}"'
            return response
        stream = StringIO(newline="")
        writer = csv.writer(stream)
        exported_at = timezone.now()
        for label, value in (
            ("Search Location", context["location"]),
            ("Search Latitude", context["latitude"]),
            ("Search Longitude", context["longitude"]),
            ("Search Radius (m)", context["radius"]),
            ("Category", context["category"]),
            ("Business Data Providers", context["provider"]),
            ("Search Depth", context["search_depth"]),
            ("Total Businesses", len(payloads)),
            ("Searched At", context["searched_at"]),
            ("Exported At", exported_at.isoformat()),
        ):
            writer.writerow([sanitize_spreadsheet_value(label), sanitize_spreadsheet_value(value)])
        writer.writerow([])
        fields = ["Business Name", "Address", "Distance (km)", "Phone", "Email", "Website", "Brand", "Rating", "Reviews", "Latitude", "Longitude", "Provider", "Enrichment Status", "All Business Emails", "Business Email Source URLs", "All Business Phones", "Business Phone Source URLs", "WhatsApp Numbers", "WhatsApp Status", "WhatsApp Source URLs", "LinkedIn", "LinkedIn Source URL", "Facebook", "Facebook Source URL", "Instagram", "Instagram Source URL", "Decision Makers", "Decision Maker Source URLs"]
        writer.writerow(fields)
        for item in payloads:
            writer.writerow([sanitize_spreadsheet_value(value) for value in csv_export_values(item)])
        response = HttpResponse("\ufeff" + stream.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{export_filename(search.location_name, "csv", exported_at)}"'
        return response


class ExcelExportView(ExportView):
    export_format = "excel"


class ImportPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error = organization_or_response(request)
        if error: return error
        serializer = SearchBusinessIdsSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        search, businesses = scoped_search_businesses(organization, serializer.validated_data)
        if search is None: return Response({"detail": "Search not found."}, status=404)
        return Response({"results": preview_import(organization, businesses)})


class ImportLeadsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error = organization_or_response(request)
        if error: return error
        serializer = ImportSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        search, businesses = scoped_search_businesses(organization, serializer.validated_data)
        if search is None: return Response({"detail": "Search not found."}, status=404)
        try:
            outcomes = import_businesses(organization, request.user, businesses, serializer.validated_data["service_id"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"results": outcomes}, status=status.HTTP_201_CREATED)


class WhatsAppContactPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error = organization_or_response(request)
        if error: return error
        serializer = SearchBusinessIdsSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        search, businesses = scoped_search_businesses(organization, serializer.validated_data)
        if search is None: return Response({"detail": "Search not found."}, status=404)
        return Response({"results": preview_whatsapp_contacts(organization, businesses)})


class WhatsAppContactImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error = organization_or_response(request)
        if error: return error
        serializer = SearchBusinessIdsSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        search, businesses = scoped_search_businesses(organization, serializer.validated_data)
        if search is None: return Response({"detail": "Search not found."}, status=404)
        return Response({"results": import_whatsapp_contacts(organization, request.user, businesses)}, status=status.HTTP_201_CREATED)
