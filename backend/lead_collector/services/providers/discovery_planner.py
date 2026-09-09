"""Deterministic, bounded Browser Search discovery planning."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveryQuery:
    term: str
    latitude: float
    longitude: float
    is_center: bool
    term_index: int
    point_index: int


def generate_grid_points(latitude, longitude, radius_m, *, enabled=True, max_points=9):
    """Return center-first origins covering the radius without changing its semantics."""
    center = (float(latitude), float(longitude))
    if not enabled or radius_m <= 2_000 or max_points <= 1:
        return [center]
    target = 5 if radius_m <= 2_500 else min(9, max_points)
    count = min(target, max(1, int(max_points)))
    # Keep origins inside 55% of the requested radius; the original point remains authoritative.
    offset_m = float(radius_m) * 0.55
    lat_step = offset_m / 111_320
    cosine = max(abs(math.cos(math.radians(center[0]))), 0.01)
    lng_step = offset_m / (111_320 * cosine)
    offsets = [
        (0, 0), (lat_step, 0), (0, lng_step), (-lat_step, 0), (0, -lng_step),
        (lat_step, lng_step), (lat_step, -lng_step),
        (-lat_step, lng_step), (-lat_step, -lng_step),
    ]
    points = []
    for lat_offset, lng_offset in offsets:
        point = (round(center[0] + lat_offset, 7), round(center[1] + lng_offset, 7))
        if point not in points:
            points.append(point)
        if len(points) == count:
            break
    return points


def build_query_plan(terms, points, *, max_terms=4, max_queries=12):
    """Prioritize center terms, then outer primary, then outer secondary searches."""
    normalized_terms = []
    for term in terms:
        cleaned = ' '.join(str(term).split())
        if cleaned and cleaned.casefold() not in {item.casefold() for item in normalized_terms}:
            normalized_terms.append(cleaned)
        if len(normalized_terms) >= max(1, int(max_terms)):
            break
    if not normalized_terms or not points:
        return []
    candidates = []
    # Center + all terms.
    for term_index, term in enumerate(normalized_terms):
        candidates.append(DiscoveryQuery(term, *points[0], True, term_index, 0))
    # Surrounding origins + primary term.
    for point_index, point in enumerate(points[1:], 1):
        candidates.append(DiscoveryQuery(normalized_terms[0], *point, False, 0, point_index))
    # Surrounding origins + secondary terms, term-major for deterministic value ordering.
    for term_index, term in enumerate(normalized_terms[1:], 1):
        for point_index, point in enumerate(points[1:], 1):
            candidates.append(DiscoveryQuery(term, *point, False, term_index, point_index))
    return candidates[:max(1, int(max_queries))]
