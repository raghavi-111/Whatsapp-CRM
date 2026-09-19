from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase

from lead_collector.services.geocoding.nominatim import rank_location_results, search_locations


def location(name, latitude, longitude, *, provider_id=None, importance=0.5, location_type="city", display_name=None):
    return {"name": name, "display_name": display_name or name, "secondary_name": "", "latitude": latitude, "longitude": longitude, "type": location_type, "class": "place", "provider_id": provider_id, "importance": importance}


class LocationRankingTests(SimpleTestCase):
    def test_deduplicates_by_provider_id_and_exact_location_signature(self):
        first = location("Vij", 57.70, 12.00, provider_id=10, display_name="Vij, Sweden")
        duplicate_id = {**first, "display_name": "Vij duplicate"}
        duplicate_signature = {**first, "provider_id": 11}
        self.assertEqual(rank_location_results([first, duplicate_id, duplicate_signature], "vij"), [first])

    def test_relevance_beats_weak_global_substrings(self):
        weak = location("Somewhere", 1, 2, importance=0.99, display_name="Road to Vijayawada, Elsewhere")
        vijayawada = location("Vijayawada", 16.5, 80.6, importance=0.6)
        self.assertIs(rank_location_results([weak, vijayawada], "vijayawada")[0], vijayawada)
        for query, expected in (("chennai", "Chennai"), ("delhi", "Delhi"), ("dubai", "Dubai"), ("london", "London")):
            exact = location(expected, 1, 1)
            self.assertIs(rank_location_results([weak, exact], query)[0], exact)

    def test_relevant_airports_remain_eligible_and_rank_highly(self):
        airport = location("Chennai International Airport", 12.99, 80.17, location_type="aerodrome")
        weak = location("Unrelated", 1, 2, importance=0.99, display_name="Chennai Street, Elsewhere")
        self.assertIs(rank_location_results([weak, airport], "chennai")[0], airport)

    @patch("lead_collector.services.geocoding.nominatim.requests.get")
    def test_provider_candidates_are_ranked_then_limited(self, get):
        cache.clear(); response = Mock(status_code=200)
        response.json.return_value = [{"place_id": index, "name": f"London {index}", "display_name": f"London {index}, United Kingdom", "lat": "51.5", "lon": str(-0.1 + index / 1000), "importance": 0.9 - index / 100, "type": "city", "address": {"country": "United Kingdom"}} for index in range(12)]
        get.return_value = response
        results = search_locations("london")
        self.assertEqual(len(results), 8)
        self.assertEqual(get.call_args.kwargs["params"]["limit"], 20)
