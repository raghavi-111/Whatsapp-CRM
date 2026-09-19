import assert from "node:assert/strict";
import test from "node:test";

import {
  ADVANCED_SEARCH_DEFAULT_OPEN, availableProviders, buildSearchPayload, contactStatus,
  coordinatesFromLocation, coordinatesFromMap, dataCoverage, effectiveSearchDepth, mappableBusinesses,
  enrichmentSummary, mapSearchArea, mergeBusinesses, operationLabel, providerSources, providerStatus, resolveSearchCenter, SEARCH_DEPTHS, searchAreaBounds, toggleSelection,
  isLatestLocationRequest, shouldSearchLocation, validateCoordinates,
} from "./leadCollectorHelpers.js";

test("provider provenance preserves every distinct source", () => {
  assert.deepEqual(providerSources({ sources: ["Browser Search", "OpenStreetMap", "Browser Search"] }), ["Browser Search", "OpenStreetMap"]);
  assert.deepEqual(providerSources({ source: "Google Places + Geoapify" }), ["Google Places", "Geoapify"]);
});

test("enrichment outcomes produce useful structured feedback", () => {
  const message = enrichmentSummary([{ status: "enriched" }, { status: "already_enriched" }, { status: "skipped_no_website" }, { status: "failed" }]);
  assert.equal(message, "Enrichment complete: 1 enriched, 1 already enriched, 1 skipped — no website, 1 failed.");
});

test("operation labels describe long Browser Search without fake progress", () => {
  assert.deepEqual(operationLabel("search", { providers: ["playwright"], search_depth: "maximum" }), { title: "Searching businesses...", detail: "Browser Search · Maximum depth · Up to ~6 min" });
  assert.equal(operationLabel("enrich").title, "Enriching selected businesses...");
  assert.equal(operationLabel("preview").title, "Checking CRM duplicates...");
});

test("all canonical Browser Search depths are accepted", () => {
  for (const depth of SEARCH_DEPTHS) assert.equal(effectiveSearchDepth(["playwright"], depth), depth);
});

test("advanced search starts collapsed and location selection populates coordinates", () => {
  assert.equal(ADVANCED_SEARCH_DEFAULT_OPEN, false);
  assert.deepEqual(coordinatesFromLocation({ latitude: 12.993374, longitude: 80.172587 }), {
    latitude: "12.993374", longitude: "80.172587", manuallyEdited: false,
  });
});

test("only the latest matching autocomplete request may update suggestions", () => {
  assert.equal(isLatestLocationRequest(3, 3, "vijayawada", "vijayawada"), true);
  assert.equal(isLatestLocationRequest(2, 3, "vij", "vijayawada"), false);
  assert.equal(isLatestLocationRequest(3, 3, "vijayawada", "hyderabad"), false);
});

test("location autocomplete requires three trimmed characters", () => {
  assert.equal(shouldSearchLocation("v"), false);
  assert.equal(shouldSearchLocation(" vi "), false);
  assert.equal(shouldSearchLocation("vij"), true);
  assert.equal(shouldSearchLocation("vijayawada"), true);
});

test("normal location searches retain all existing payload controls", () => {
  const form = { radius_m: 5000, category: "hotels_resorts", providers: ["playwright"], search_depth: "deep" };
  const location = { display_name: "Chennai, Tamil Nadu", latitude: 12.993374, longitude: 80.172587 };
  const coordinates = coordinatesFromLocation(location);
  assert.deepEqual(buildSearchPayload(form, location, coordinates), {
    location_name: "Chennai, Tamil Nadu", latitude: 12.993374, longitude: 80.172587,
    radius_m: 5000, category: "hotels_resorts", providers: ["playwright"], search_depth: "deep",
  });
});

test("valid manually edited coordinates override a selected location", () => {
  const location = { display_name: "Chennai", latitude: 13, longitude: 80 };
  const coordinates = { latitude: "48.8566", longitude: "2.3522", manuallyEdited: true };
  assert.deepEqual(resolveSearchCenter(location, coordinates), {
    latitude: 48.8566, longitude: 2.3522, locationName: "Custom coordinates", source: "manual",
  });
});

test("map-picked coordinates become the authoritative payload center", () => {
  const coordinates = coordinatesFromMap(16.62326, 80.54664);
  const center = resolveSearchCenter({ display_name: "Old location", latitude: 1, longitude: 2 }, coordinates);
  assert.deepEqual(center, { latitude: 16.62326, longitude: 80.54664, locationName: "Custom map location", source: "manual" });
  assert.deepEqual(buildSearchPayload({ radius_m: 5000, category: "hotels_resorts", providers: ["playwright"], search_depth: "quick" }, null, coordinates), { location_name: "Custom map location", latitude: 16.62326, longitude: 80.54664, radius_m: 5000, category: "hotels_resorts", providers: ["playwright"], search_depth: "quick" });
});

test("coordinate validation accepts boundaries and rejects invalid or partial pairs", () => {
  assert.equal(validateCoordinates("-90", "180").valid, true);
  assert.equal(validateCoordinates("90", "-180").valid, true);
  for (const [latitude, longitude] of [["-91", "0"], ["91", "0"], ["0", "-181"], ["0", "181"], ["north", "0"], ["0", "Infinity"]]) {
    assert.equal(validateCoordinates(latitude, longitude).valid, false);
  }
  assert.equal(validateCoordinates("12", "").errors.longitude.length > 0, true);
  assert.equal(validateCoordinates("", "80").errors.latitude.length > 0, true);
});

test("non-browser providers always use the standard server profile", () => {
  assert.equal(effectiveSearchDepth(["openstreetmap"], "maximum"), "standard");
});

test("map data excludes missing coordinates", () => {
  assert.deepEqual(mappableBusinesses([{ id: 1, latitude: 13, longitude: 80 }, { id: 2, latitude: null, longitude: null }]).map((item) => item.id), [1]);
});

test("map search area preserves the selected center and radius in meters", () => {
  assert.deepEqual(mapSearchArea({ latitude: 16.62326, longitude: 80.54664, radius_m: 5000 }), { center: [16.62326, 80.54664], radiusMeters: 5000 });
  assert.equal(mapSearchArea({ latitude: "12.993374", longitude: "80.172587", radius_m: 10000 }).radiusMeters, 10000);
});

test("map fitting bounds are layer-independent and safe across center and radius changes", () => {
  assert.equal(searchAreaBounds(undefined, 5000), null);
  assert.equal(searchAreaBounds([Number.NaN, 80], 5000), null);
  const first = searchAreaBounds([16.62326, 80.54664], 5000);
  const larger = searchAreaBounds([16.62326, 80.54664], 10000);
  const moved = searchAreaBounds([12.993374, 80.172587], 5000);
  assert.equal(first.length, 2);
  assert.equal(larger[1][0] > first[1][0], true);
  assert.notDeepEqual(moved, first);
});

const settings = {
  business_providers: ["openstreetmap", "playwright", "geoapify"],
  people_providers: ["official_website", "apollo"],
  providers: {
    openstreetmap: { configured: true }, playwright: { configured: true },
    geoapify: { configured: false }, official_website: { configured: true },
    apollo: { configured: false }, google: { configured: false },
  },
};

test("provider visibility follows enabled and configured organization settings", () => {
  assert.deepEqual(availableProviders(settings).map((item) => item.id), ["openstreetmap", "playwright"]);
  assert.deepEqual(availableProviders(settings, "people").map((item) => item.id), ["official_website"]);
  assert.equal(providerStatus(settings, "geoapify").usable, false);
  assert.equal(providerStatus(settings, "google").enabled, false);
});

test("search summary data coverage returns counts and percentages", () => {
  const coverage = dataCoverage([{ address: "A", phone: "1", email: null }, { address: "B", phone: null, email: "a@b.test", website: "https://b.test" }]);
  assert.deepEqual(coverage.find((item) => item.field === "address"), { field: "address", label: "Address", count: 2, percentage: 100 });
  assert.equal(coverage.find((item) => item.field === "phone").percentage, 50);
  assert.equal(dataCoverage([])[0].percentage, 0);
});

test("selection supports row toggle select-all and clear semantics", () => {
  assert.deepEqual(toggleSelection([], 1), [1]);
  assert.deepEqual(toggleSelection([1, 2], 1), [2]);
  assert.deepEqual([1, 2, 3], [1, 2, 3]);
  assert.deepEqual([], []);
});

test("result merging preserves rows and missing optional fields remain safe", () => {
  const merged = mergeBusinesses([{ id: 1, name: "A" }, { id: 2, name: "B" }], [{ id: 2, name: "B", email: "b@test.invalid" }]);
  assert.equal(merged[1].email, "b@test.invalid");
  assert.equal(contactStatus({}), "Not enriched");
  assert.equal(contactStatus({ website: "https://example.test" }), "Partial");
});
