"""Central, server-controlled Browser Search depth profiles."""

from dataclasses import dataclass


SEARCH_DEPTHS = ('quick', 'standard', 'deep', 'maximum')


@dataclass(frozen=True)
class SearchDepthProfile:
    time_budget_seconds: int
    max_grid_points: int
    max_terms: int
    max_queries: int
    results_per_query: int
    max_candidates: int
    max_final_results: int
    scroll_cycles: int
    zero_yield_threshold: int
    discovery_budget_fraction: float


SEARCH_DEPTH_PROFILES = {
    'quick': SearchDepthProfile(35, 1, 1, 1, 15, 20, 20, 5, 2, 0.55),
    # Matches the committed Discovery Coverage V2 defaults.
    'standard': SearchDepthProfile(150, 5, 3, 12, 20, 40, 40, 8, 3, 0.90),
    'deep': SearchDepthProfile(240, 9, 5, 24, 25, 70, 70, 12, 5, 0.62),
    'maximum': SearchDepthProfile(360, 9, 7, 48, 30, 100, 100, 16, 8, 0.60),
}


def get_search_depth_profile(depth='standard'):
    return SEARCH_DEPTH_PROFILES[depth or 'standard']
