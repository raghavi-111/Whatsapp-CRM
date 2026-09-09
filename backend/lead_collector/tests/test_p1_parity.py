from io import BytesIO
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Organization, OrganizationMember
from lead_collector.models import DiscoveredBusiness, DiscoverySearch
from lead_collector.services.enrichment.base import EnrichmentError
from lead_collector.services.enrichment.hotel_website import _social_profile_url, _validate_public_url
from lead_collector.services.providers.orchestrator import MultiProviderSearchError, search_businesses_multi_provider
from lead_collector.services.providers.orchestrator import deduplicate_businesses
from lead_collector.services.people_enrichment.orchestrator import search_decision_makers_multi_provider
from lead_collector.services.scraping.parsers import deduplicate_listings, normalize_listing
from lead_collector.services import openstreetmap


def enrichment_result(hotel, status="FOUND", **values):
    return {
        "status": status, "hotel": {**hotel, **values}, "sources": {},
        "website_confidence": "HIGH", "business_emails": [], "business_phones": [],
        "whatsapp_contacts": [], "social_profiles": {}, "social_profile_sources": {},
        "discovered_pages": {}, "decision_makers": [],
    }


class P1ServiceParityTests(SimpleTestCase):
    @patch("lead_collector.services.openstreetmap.cache")
    @patch("lead_collector.services.openstreetmap._configured_endpoints", return_value=["primary", "fallback"])
    @patch("lead_collector.services.openstreetmap._request_overpass")
    def test_openstreetmap_retries_normalizes_sorts_and_caches(self, request, _endpoints, cache):
        cache.get.return_value = None
        response = Mock(); response.json.return_value = {"elements": [
            {"type": "node", "id": 2, "lat": 13.01, "lon": 80, "tags": {"name": "Far", "phone": "+912"}},
            {"type": "node", "id": 1, "lat": 13, "lon": 80, "tags": {"name": "Near", "contact:email": "near@example.test"}},
        ]}
        request.side_effect = [openstreetmap.OpenStreetMapError("timeout", retryable=True), response]
        result = openstreetmap.search_nearby_businesses(13, 80, 1000, "cafes")
        self.assertEqual([item["name"] for item in result], ["Near", "Far"])
        self.assertEqual(result[0]["email"], "near@example.test")
        self.assertEqual(request.call_count, 2)
        cache.set.assert_called_once()

    def test_browser_card_normalization_and_branch_safe_deduplication(self):
        url = "https://www.google.com/maps/place/Acme/@13.1,80.2,17z?query_place_id=place-1"
        listing = normalize_listing({"name": "Acme", "address": "Address: North", "phone": "Phone: +91 90000 00000", "rating": "4.5", "review_count": "(1,234)", "maps_url": url}, "cafes")
        self.assertEqual((listing["place_id"], listing["latitude"], listing["longitude"], listing["review_count"]), ("place-1", 13.1, 80.2, 1234))
        other_branch = {**listing, "id": "place-2", "place_id": "place-2", "address": "South", "latitude": 14}
        self.assertEqual(len(deduplicate_listings([listing, dict(listing), other_branch])), 2)

    def test_provider_deduplication_merges_evidence_by_priority_without_merging_distant_branches(self):
        merged = deduplicate_businesses([
            {"name": "Acme", "website": "https://acme.example", "phone": "osm", "source": "OpenStreetMap", "sources": ["OpenStreetMap"], "_provider": "openstreetmap", "distance_km": 1},
            {"name": "Acme Ltd", "website": "https://acme.example/contact", "phone": "google", "email": "info@acme.example", "source": "Google Places", "sources": ["Google Places"], "_provider": "google", "distance_km": 1},
        ])
        self.assertEqual(len(merged), 1)
        self.assertEqual((merged[0]["phone"], merged[0]["email"]), ("google", "info@acme.example"))
        branches = deduplicate_businesses([
            {"name": "Acme", "address": "North", "latitude": 13, "longitude": 80, "source": "OpenStreetMap", "sources": ["OpenStreetMap"], "_provider": "openstreetmap", "distance_km": 1},
            {"name": "Acme", "address": "South", "latitude": 14, "longitude": 80, "source": "OpenStreetMap", "sources": ["OpenStreetMap"], "_provider": "openstreetmap", "distance_km": 100},
        ])
        self.assertEqual(len(branches), 2)

    @patch("lead_collector.services.people_enrichment.orchestrator.get_people_provider")
    def test_people_provider_selection_merge_priority_and_partial_failure(self, factory):
        official = Mock(); official.search_decision_makers.return_value = {"contacts": [{"name": "Jane", "title": "General Manager", "role_group": "general_manager", "organization_name": "Acme", "business_email": "public@acme.example", "source_url": "https://acme.example/team"}]}
        apollo = Mock(); apollo.search_decision_makers.return_value = {"contacts": [{"name": "Jane", "title": "General Manager", "role_group": "general_manager", "organization_name": "Acme", "business_email": "verified@acme.example", "verification_status": "verified", "linkedin_url": "https://linkedin.com/in/jane"}]}
        zoominfo = Mock(); zoominfo.search_decision_makers.side_effect = RuntimeError("secret-token")
        factory.side_effect = lambda name, _settings: {"official_website": official, "apollo": apollo, "zoominfo": zoominfo}[name]
        settings = Mock(people_providers=["official_website", "apollo", "zoominfo"])
        result = search_decision_makers_multi_provider({"name": "Acme"}, "hotels_resorts", ["official_website", "apollo", "zoominfo"], settings)
        self.assertEqual(result["status"], "FOUND")
        self.assertEqual(result["provider_results"]["zoominfo"], {"status": "error"})
        self.assertEqual(result["contacts"][0]["business_email"], "verified@acme.example")
        self.assertEqual(factory.call_count, 3)

    @patch("lead_collector.services.providers.orchestrator.get_business_provider")
    def test_discovery_preserves_partial_provider_success_and_all_failures_are_typed(self, factory):
        success = Mock(); success.search_nearby_businesses.return_value = [{"name": "Cafe", "latitude": 13, "longitude": 80}]
        failure = Mock(); failure.search_nearby_businesses.side_effect = RuntimeError("credential=secret")
        factory.side_effect = [success, failure]
        settings = Mock(business_providers=["openstreetmap", "playwright"])
        result = search_businesses_multi_provider(13, 80, 1000, "cafes", ["openstreetmap", "playwright"], settings)
        self.assertEqual([item["name"] for item in result["hotels"]], ["Cafe"])
        self.assertEqual(result["provider_results"]["playwright"], {"status": "error"})
        factory.side_effect = [failure, failure]
        with self.assertRaises(MultiProviderSearchError):
            search_businesses_multi_provider(13, 80, 1000, "cafes", ["openstreetmap", "playwright"], settings)

    @patch("lead_collector.services.enrichment.hotel_website.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 0))])
    def test_crawler_blocks_private_destinations_and_social_urls_reject_non_profiles(self, _dns):
        with self.assertRaises(EnrichmentError):
            _validate_public_url("http://localhost/private")
        self.assertEqual(_social_profile_url("https://linkedin.com/login"), (None, None))
        self.assertEqual(_social_profile_url("https://facebook.com/sharer/sharer.php"), (None, None))
        self.assertEqual(_social_profile_url("https://instagram.example.com/acme"), (None, None))
        self.assertEqual(_social_profile_url("https://www.linkedin.com/company/acme/")[0], "linkedin")


class P1EndpointParityTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="p1@example.com", password="pass")
        self.org = Organization.objects.create(name="P1", slug="p1", owner=self.user)
        OrganizationMember.objects.create(organization=self.org, user=self.user, role="owner", status="active")
        self.search = DiscoverySearch.objects.create(
            organization=self.org, created_by=self.user, location_name="Pune International Airport",
            latitude=18.5793, longitude=73.9089, radius_m=5000, category="hotels_resorts",
            providers=["openstreetmap", "playwright"], search_depth="deep", status="complete",
        )
        self.client.force_authenticate(self.user)

    def business(self, key, payload, search=None):
        return DiscoveredBusiness.objects.create(
            organization=self.org, search=search or self.search, identity_key=key,
            name=payload["name"], payload=payload,
        )

    @patch("lead_collector.services.export.enrichment.enrich_hotels_bulk")
    def test_manual_enrichment_is_bounded_eligible_persisted_and_failure_isolated(self, bulk):
        good = self.business("good", {"name": "Good", "website": "https://good.example"})
        failed = self.business("failed", {"name": "Failed", "website": "https://failed.example"})
        complete = self.business("complete", {"name": "Complete", "website": "https://complete.example", "enrichment_status": "FOUND", "business_emails": [], "business_phones": [], "social_profiles": {}, "decision_makers": []})
        no_site = self.business("no-site", {"name": "No Site"})
        bulk.return_value = {"results": [
            enrichment_result(good.payload, email="hello@good.example"),
            enrichment_result(failed.payload, status="ERROR"),
        ]}
        response = self.client.post("/api/lead-collector/businesses/enrich/", {
            "business_ids": [good.id, failed.id, complete.id, no_site.id], "search_id": self.search.id,
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["status"] for row in response.data["outcomes"]], ["enriched", "failed", "already_enriched", "skipped_no_website"])
        self.assertEqual([item["name"] for item in bulk.call_args.args[0]], ["Good", "Failed"])
        good.refresh_from_db(); complete.refresh_from_db(); no_site.refresh_from_db()
        self.assertEqual(good.payload["email"], "hello@good.example")
        self.assertEqual(complete.payload["enrichment_status"], "FOUND")
        self.assertNotIn("enrichment_status", no_site.payload)

    @patch("lead_collector.views.search_decision_makers_multi_provider")
    def test_decision_maker_unexpected_failure_does_not_abort_other_businesses(self, people):
        first = self.business("first", {"name": "First", "website": "https://first.example"})
        second = self.business("second", {"name": "Second", "website": "https://second.example"})
        people.side_effect = [RuntimeError("secret transport detail"), {"contacts": [{"name": "Jane", "title": "Manager"}], "status": "FOUND", "provider_results": {}}]
        response = self.client.post("/api/lead-collector/businesses/decision-makers/", {
            "business_ids": [first.id, second.id], "search_id": self.search.id,
            "providers": ["official_website"],
        }, format="json")
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual(first.payload["decision_maker_status"], "ERROR")
        self.assertEqual(second.payload["decision_makers"][0]["name"], "Jane")

    def test_exports_use_authoritative_search_summary_and_reject_mixed_search_rows(self):
        item = self.business("unicode", {"name": "Unicode Café", "phone": "+91 90000 00000", "enrichment_status": "FOUND", "business_emails": [], "business_phones": [], "social_profiles": {}, "decision_makers": []})
        other_search = DiscoverySearch.objects.create(organization=self.org, created_by=self.user, location_name="Old", latitude=1, longitude=2, radius_m=1000, category="cafes", providers=["openstreetmap"], status="complete")
        stale = self.business("stale", {"name": "Stale", "phone": "+91 91111 11111"}, other_search)
        request = {"business_ids": [item.id, stale.id], "context": {"id": self.search.id, "location_name": "Untrusted"}}
        csv_response = self.client.post("/api/lead-collector/exports/csv/", request, format="json")
        csv_text = csv_response.content.decode("utf-8-sig")
        self.assertIn("Search Location,Pune International Airport", csv_text)
        self.assertIn("Category,hotels_resorts", csv_text)
        self.assertIn("Search Depth,deep", csv_text)
        self.assertIn("Unicode Café", csv_text)
        self.assertNotIn("Stale", csv_text)
        excel_response = self.client.post("/api/lead-collector/exports/excel/", request, format="json")
        workbook = load_workbook(BytesIO(excel_response.content), read_only=True)
        summary = dict(workbook["Search Summary"].values)
        self.assertEqual(summary["Location"], "Pune International Airport")
        self.assertEqual(summary["Category"], "hotels_resorts")
        self.assertEqual(summary["Search Depth"], "deep")
        self.assertEqual(summary["Total Businesses"], 1)

    def test_state_changing_endpoints_reject_foreign_search_context(self):
        item = self.business("owned", {"name": "Owned", "website": "https://owned.example", "phone": "+91 90000 00000"})
        other = Organization.objects.create(name="Other", slug="other-p1", owner=self.user)
        foreign_search = DiscoverySearch.objects.create(organization=other, created_by=self.user, location_name="Other", latitude=1, longitude=2, radius_m=1000, category="cafes", providers=["openstreetmap"], status="complete")
        for endpoint, extra in (
            ("/api/lead-collector/businesses/enrich/", {}),
            ("/api/lead-collector/businesses/decision-makers/", {"providers": ["official_website"]}),
            ("/api/lead-collector/imports/preview/", {}),
        ):
            response = self.client.post(endpoint, {"business_ids": [item.id], "search_id": foreign_search.id, **extra}, format="json")
            self.assertEqual(response.status_code, 404)
