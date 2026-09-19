from django.conf import settings

from lead_collector.business_categories import get_business_category
from lead_collector.services.openstreetmap import calculate_distance_km

from ..scraping import MapsScraper, ScraperError
from .base import HotelProvider
from .discovery_planner import build_query_plan, generate_grid_points
from .search_depth import get_search_depth_profile


class PlaywrightProviderError(Exception):
    """Raised when browser-backed business discovery fails safely."""


CATEGORY_SEARCH_TERMS = {
    'hotels_resorts': ('hotels', 'resorts', 'business hotels', 'airport hotels', 'budget hotels', 'luxury hotels', 'boutique hotels'),
    'cafes': ('cafes', 'coffee shops', 'coffee houses'),
    'restaurants': ('restaurants', 'family restaurants', 'casual dining', 'vegetarian restaurants', 'non vegetarian restaurants', 'fine dining restaurants'),
    'shopping_malls': ('shopping malls', 'shopping centers', 'retail malls'),
    'hospitals': ('hospitals', 'multispeciality hospitals', 'general hospitals', 'medical centers'),
    'coworking_spaces': ('coworking spaces', 'shared offices', 'business centers', 'flexible offices'),
    'salons_spas': ('salons', 'spas', 'beauty salons', 'hair salons', 'wellness spas'),
    'gyms_fitness': ('gyms', 'fitness centers', 'health clubs', 'fitness studios'),
    'universities_colleges': ('universities', 'colleges', 'degree colleges', 'technical colleges'),
    'schools': ('schools', 'international schools', 'private schools', 'CBSE schools', 'public schools', 'high schools'),
    'airports': ('airports',),
    'retail': ('retail stores', 'shopping stores', 'department stores', 'clothing stores'),
    'event_venues': ('event venues', 'banquet halls', 'convention centers'),
    'banks': ('banks', 'bank branches', 'commercial banks'),
    'petrol_stations': ('petrol stations', 'fuel stations', 'gas stations'),
    'pharmacies': ('pharmacies', 'medical stores', 'chemists'),
    'hostels': ('hostels', 'student hostels', 'backpacker hostels'),
}
# Backward-compatible primary-term view for integrations importing the old constant.
MAPS_CATEGORY_QUERIES = {
    category: terms[0] for category, terms in CATEGORY_SEARCH_TERMS.items()
}


class PlaywrightProvider(HotelProvider):
    def __init__(self, scraper=None):
        self.scraper = scraper or MapsScraper()

    def search_nearby_hotels(self, latitude, longitude, radius):
        return self.search_nearby_businesses(latitude, longitude, radius, 'hotels_resorts')

    def search_nearby_businesses(
        self, latitude, longitude, radius, category='hotels_resorts', search_depth='standard'
    ):
        get_business_category(category)
        profile = get_search_depth_profile(search_depth)
        queries = CATEGORY_SEARCH_TERMS[category][:profile.max_terms]
        points = generate_grid_points(
            latitude, longitude, radius, enabled=settings.PLAYWRIGHT_GRID_ENABLED,
            max_points=profile.max_grid_points,
        )
        query_plan = build_query_plan(
            queries, points, max_terms=profile.max_terms, max_queries=profile.max_queries,
        )
        try:
            results = self.scraper.search_many(
                queries=queries, latitude=latitude, longitude=longitude, category=category,
                query_plan=query_plan,
                radius_m=radius,
                max_results_per_query=profile.results_per_query,
                max_total_results=profile.max_candidates,
                scroll_cycles=profile.scroll_cycles,
                zero_yield_threshold=profile.zero_yield_threshold,
                time_budget_seconds=profile.time_budget_seconds,
                discovery_budget_fraction=profile.discovery_budget_fraction,
            )
        except (ScraperError, ValueError, TypeError) as exc:
            raise PlaywrightProviderError('Browser business search failed.') from exc
        for result in results:
            result['distance_km'] = calculate_distance_km(latitude, longitude, result.get('latitude'), result.get('longitude'))
        invalid_coordinates = sum(result.get('distance_km') is None for result in results)
        outside_radius = sum(
            result.get('distance_km') is not None and result['distance_km'] > radius / 1000
            for result in results
        )
        filtered = [
            result for result in results
            if result.get('distance_km') is None or result['distance_km'] <= radius / 1000
        ]
        final = filtered[:profile.max_final_results]
        scraper_counts = getattr(self.scraper, 'last_search_counts', {})
        if not isinstance(scraper_counts, dict):
            scraper_counts = {}
        self.last_discovery_metrics = {
            'search_depth': search_depth, 'time_budget_seconds': profile.time_budget_seconds,
            'elapsed_seconds': scraper_counts.get('elapsed_seconds', 0),
            'grid_points_generated': len(points), 'grid_points_used': len({
                (query.latitude, query.longitude) for query in query_plan
            }),
            'terms_available': len(CATEGORY_SEARCH_TERMS[category]),
            'terms_used': len(queries), 'terms_planned': len(queries),
            'queries_planned': len(query_plan),
            'raw_cards_collected': scraper_counts.get('combined', 0),
            'unique_before_details': scraper_counts.get('unique', len(results)),
            'detail_records_completed': len(results),
            'duplicates_removed': scraper_counts.get('duplicates_removed', 0),
            'invalid_coordinates': invalid_coordinates,
            'outside_radius': outside_radius + scraper_counts.get('raw_outside_radius', 0),
            'final_results': len(final),
            'budget_exhausted': scraper_counts.get('budget_exhausted', False),
            'early_stop_reason': scraper_counts.get('early_stop_reason'),
            'queries_skipped': scraper_counts.get('queries_skipped', 0),
            'detail_attempts': scraper_counts.get('detail_attempts', len(results)),
            'detail_successes': scraper_counts.get('detail_successes', len(results)),
            **{key: scraper_counts.get(key, 0) for key in (
                'queries_executed', 'queries_succeeded', 'queries_failed'
            )},
        }
        return final
