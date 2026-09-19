import logging
import time
from urllib.parse import quote_plus

from django.conf import settings
from lead_collector.services.openstreetmap import calculate_distance_km

from .browser import BrowserStartupError, browser_page
from .parsers import coordinates_from_url, deduplicate_listings, listing_identity, normalize_listing


logger = logging.getLogger(__name__)
MAPS_SEARCH_URL = 'https://www.google.com/maps/search/{query}/@{latitude},{longitude},13z'
SELECTORS = {
    'feed': '[role="feed"]', 'card': '[role="feed"] > div:has(a[href*="/maps/place/"])',
    'card_link': 'a[href*="/maps/place/"]', 'rating': '[role="img"][aria-label*="star"]',
    'no_results': '[role="main"]',
}
DETAIL_SELECTORS = {
    'address': ('button[data-item-id="address"]', '[aria-label^="Address:"]'),
    'phone': ('button[data-item-id^="phone:"]', '[aria-label^="Phone:"]'),
    'website': ('a[data-item-id="authority"]', 'a[aria-label^="Website:"]'),
    'opening_hours': ('button[data-item-id="oh"]', '[aria-label*="hours" i]'),
    'review_count': (
        'button[jsaction*="rating.moreReviews"]',
        'button[aria-label*="review" i]',
    ),
}
DETAIL_READY_TIMEOUT_MS = 2_000


class ScraperError(Exception):
    """Controlled browser-search provider failure."""


class MapsScraper:
    def __init__(self, page_factory=browser_page):
        self.page_factory = page_factory

    def search(self, *, query, latitude, longitude, category, max_results=None):
        limit = max_results or settings.PLAYWRIGHT_MAX_RESULTS
        url = MAPS_SEARCH_URL.format(query=quote_plus(query), latitude=latitude, longitude=longitude)
        try:
            with self.page_factory(headless=settings.PLAYWRIGHT_HEADLESS, timeout=settings.PLAYWRIGHT_TIMEOUT) as page:
                page.goto(url, wait_until='domcontentloaded')
                feed = page.locator(SELECTORS['feed'])
                try:
                    feed.wait_for(state='visible')
                except Exception as exc:
                    if page.get_by_text('No results found', exact=False).count():
                        return []
                    raise exc
                self._collect_cards(page, feed, limit)
                return self._extract_results(page, category, limit)
        except BrowserStartupError as exc:
            raise ScraperError(str(exc)) from exc
        except Exception as exc:
            if exc.__class__.__name__ == 'TimeoutError':
                raise ScraperError('Business search page timed out.') from exc
            raise ScraperError('Business search page could not be processed.') from exc

    def search_many(
        self, *, queries, latitude, longitude, category,
        max_results_per_query=None, max_total_results=None, query_plan=None, radius_m=None,
        scroll_cycles=8, zero_yield_threshold=3, time_budget_seconds=None,
        discovery_budget_fraction=0.68,
    ):
        per_query_limit = max_results_per_query or settings.PLAYWRIGHT_MAX_RESULTS_PER_QUERY
        total_limit = max_total_results or settings.PLAYWRIGHT_MAX_TOTAL_RESULTS
        raw_listings, query_results, seen_identities = [], {}, set()
        started = time.monotonic()
        query_deadline = (
            started + time_budget_seconds * discovery_budget_fraction
            if time_budget_seconds else None
        )
        budget_exhausted = False
        early_stop_reason = None
        try:
            with self.page_factory(
                headless=settings.PLAYWRIGHT_HEADLESS, timeout=settings.PLAYWRIGHT_TIMEOUT
            ) as page:
                legacy_plan = query_plan is None
                plan = query_plan or [
                    type('Query', (), {'term': query, 'latitude': latitude, 'longitude': longitude,
                                       'is_center': True})
                    for query in queries
                ]
                consecutive_empty = 0
                for index, planned in enumerate(plan):
                    query = planned.term
                    diagnostic_key = query if legacy_plan else (
                        f'{query}@{planned.latitude:.7f},{planned.longitude:.7f}'
                    )
                    if query_deadline is not None and time.monotonic() >= query_deadline:
                        early_stop_reason = 'detail_budget_reserve'
                        query_results[diagnostic_key] = {'status': 'skipped', 'count': 0, 'unique_added': 0}
                        continue
                    if index and not planned.is_center and consecutive_empty >= zero_yield_threshold:
                        early_stop_reason = 'zero_yield'
                        query_results[diagnostic_key] = {
                            'status': 'skipped', 'count': 0, 'unique_added': 0,
                        }
                        continue
                    try:
                        cards = self._search_cards(
                            page, query, planned.latitude, planned.longitude, per_query_limit,
                            scroll_cycles=scroll_cycles,
                        )
                        raw_listings.extend(cards)
                        unique_added = 0
                        for card in cards:
                            identity = listing_identity(card)
                            if identity not in seen_identities:
                                seen_identities.add(identity)
                                unique_added += 1
                        consecutive_empty = consecutive_empty + 1 if unique_added == 0 else 0
                        query_results[diagnostic_key] = {
                            'status': 'success', 'count': len(cards),
                            'unique_added': unique_added,
                        }
                    except Exception:
                        logger.info('Browser category query failed: %s', query, exc_info=True)
                        query_results[diagnostic_key] = {
                            'status': 'error', 'count': 0, 'unique_added': 0,
                        }
                if not any(item['status'] == 'success' for item in query_results.values()):
                    raise ScraperError('All browser category queries failed.')
                deduplicated_raw = self._deduplicate_raw_listings(raw_listings)
                radius_eligible, raw_outside_radius = [], 0
                for raw in deduplicated_raw:
                    candidate_latitude, candidate_longitude = coordinates_from_url(
                        raw.get('maps_url') or raw.get('google_maps_url')
                    )
                    distance = calculate_distance_km(
                        latitude, longitude, candidate_latitude, candidate_longitude
                    )
                    if radius_m is not None and distance is not None and distance > radius_m / 1000:
                        raw_outside_radius += 1
                    else:
                        radius_eligible.append(raw)
                unique_raw = radius_eligible[:total_limit]
                self._detail_deadline = (started + time_budget_seconds) if time_budget_seconds else None
                results = self._extract_raw_results(page, unique_raw, category)
                detail_attempts = getattr(self, '_last_detail_attempts', len(results))
                detail_successes = getattr(self, '_last_detail_successes', len(results))
                if time_budget_seconds and time.monotonic() >= started + time_budget_seconds:
                    budget_exhausted, early_stop_reason = True, 'time_budget'
        except BrowserStartupError as exc:
            raise ScraperError(str(exc)) from exc
        except ScraperError:
            raise
        except Exception as exc:
            raise ScraperError('Business search page could not be processed.') from exc
        self.last_query_results = query_results
        self.last_search_counts = {
            'combined': len(raw_listings), 'unique': len(unique_raw),
            'returned': len(results), 'queries_planned': len(plan),
            'queries_executed': sum(item['status'] != 'skipped' for item in query_results.values()),
            'queries_succeeded': sum(item['status'] == 'success' for item in query_results.values()),
            'queries_failed': sum(item['status'] == 'error' for item in query_results.values()),
            'duplicates_removed': len(raw_listings) - len(deduplicated_raw),
            'raw_outside_radius': raw_outside_radius,
            'queries_skipped': sum(item['status'] == 'skipped' for item in query_results.values()),
            'detail_attempts': detail_attempts, 'detail_successes': detail_successes,
            'elapsed_seconds': round(time.monotonic() - started, 2),
            'budget_exhausted': budget_exhausted, 'early_stop_reason': early_stop_reason,
        }
        return results[:total_limit]

    def _search_cards(self, page, query, latitude, longitude, limit, scroll_cycles=8):
        url = MAPS_SEARCH_URL.format(
            query=quote_plus(query), latitude=latitude, longitude=longitude
        )
        page.goto(url, wait_until='domcontentloaded')
        feed = page.locator(SELECTORS['feed'])
        try:
            feed.wait_for(state='visible')
        except Exception:
            if page.get_by_text('No results found', exact=False).count():
                return []
            raise
        self._collect_cards(page, feed, limit, scroll_cycles=scroll_cycles)
        return self._extract_raw_cards(page, limit)

    def _extract_raw_cards(self, page, limit):
        raw_listings, cards = [], page.locator(SELECTORS['card'])
        for index in range(min(cards.count(), limit)):
            try:
                card = cards.nth(index)
                link = card.locator(SELECTORS['card_link']).first
                raw_listings.append({
                    'name': link.get_attribute('aria-label'),
                    'maps_url': link.get_attribute('href'),
                    'rating': self._attribute(card, SELECTORS['rating'], 'aria-label'),
                    'review_count': card.inner_text(),
                })
            except Exception:
                logger.info('Skipping a listing card that could not be parsed.', exc_info=True)
        return raw_listings

    @staticmethod
    def _deduplicate_raw_listings(raw_listings):
        unique, keys = [], set()
        for raw in raw_listings:
            key = listing_identity(raw)
            if key not in keys:
                keys.add(key)
                unique.append(raw)
        return unique

    def _extract_raw_results(self, page, raw_listings, category):
        results, attempts, successes = [], 0, 0
        deadline = getattr(self, '_detail_deadline', None)
        for raw in raw_listings:
            if deadline is not None and time.monotonic() >= deadline:
                break
            try:
                attempts += 1
                try:
                    self.open_listing(page, raw['maps_url'])
                    raw.update(self.extract_listing_details(page))
                    successes += 1
                except Exception:
                    logger.info('Listing details were unavailable; keeping card data.', exc_info=True)
                normalized = normalize_listing(raw, category)
                if normalized:
                    results.append(normalized)
            except Exception:
                logger.info('Skipping a listing that could not be parsed.', exc_info=True)
        results = deduplicate_listings(results)
        self._last_detail_attempts, self._last_detail_successes = attempts, successes
        return results

    def _collect_cards(self, page, feed, limit, scroll_cycles=8):
        previous = -1
        for _ in range(scroll_cycles):
            count = page.locator(SELECTORS['card']).count()
            if count >= limit or count == previous:
                break
            previous = count
            feed.evaluate('(element) => element.scrollBy(0, element.scrollHeight)')
            page.wait_for_timeout(400)

    def _extract_results(self, page, category, limit):
        return self._extract_raw_results(
            page, self._extract_raw_cards(page, limit), category
        )[:limit]

    def open_listing(self, page, maps_url):
        page.goto(maps_url, wait_until='domcontentloaded')
        page.locator('h1').first.wait_for(state='visible')
        ready_selector = ', '.join(
            selector for selectors in DETAIL_SELECTORS.values() for selector in selectors
        )
        try:
            page.locator(ready_selector).first.wait_for(
                state='attached', timeout=DETAIL_READY_TIMEOUT_MS,
            )
        except Exception:
            # A valid listing can legitimately expose none of these optional fields.
            pass

    def extract_listing_details(self, page):
        return {
            'address': self._first_attribute(page, DETAIL_SELECTORS['address'], 'aria-label'),
            'phone': self._first_attribute(page, DETAIL_SELECTORS['phone'], 'aria-label'),
            'website': self._first_attribute(page, DETAIL_SELECTORS['website'], 'href'),
            'opening_hours': self._first_attribute(
                page, DETAIL_SELECTORS['opening_hours'], 'aria-label'
            ),
            'review_count': self._first_attribute(
                page, DETAIL_SELECTORS['review_count'], 'aria-label'
            ),
        }

    @classmethod
    def _first_attribute(cls, scope, selectors, attribute):
        for selector in selectors:
            value = cls._attribute(scope, selector, attribute)
            if value:
                return value
        return None

    @staticmethod
    def _attribute(scope, selector, attribute):
        locator = scope.locator(selector)
        return locator.first.get_attribute(attribute) if locator.count() else None
