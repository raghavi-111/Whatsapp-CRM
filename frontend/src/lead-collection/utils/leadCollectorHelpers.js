export const SEARCH_DEPTHS = ["quick", "standard", "deep", "maximum"];
export const ADVANCED_SEARCH_DEFAULT_OPEN = false;

export function isLatestLocationRequest(requestId, latestRequestId, query, currentQuery) {
  return requestId === latestRequestId && query === currentQuery.trim();
}

export function shouldSearchLocation(query) {
  return String(query ?? "").trim().length >= 3;
}

export function coordinatesFromLocation(location) {
  return {
    latitude: String(location.latitude),
    longitude: String(location.longitude),
    manuallyEdited: false,
  };
}

export function coordinatesFromMap(latitude, longitude) {
  return { latitude: String(latitude), longitude: String(longitude), manuallyEdited: true, locationName: "Custom map location" };
}

export function effectiveSearchDepth(providers, requested = "standard") {
  if (!providers.includes("playwright")) return "standard";
  return SEARCH_DEPTHS.includes(requested) ? requested : "standard";
}

export function mappableBusinesses(businesses) {
  return businesses.filter((item) =>
    item.latitude !== null && item.latitude !== undefined && item.latitude !== "" &&
    item.longitude !== null && item.longitude !== undefined && item.longitude !== "" &&
    Number.isFinite(Number(item.latitude)) && Number.isFinite(Number(item.longitude)),
  );
}

export function mapSearchArea(searchResult) {
  return {
    center: [Number(searchResult.latitude), Number(searchResult.longitude)],
    radiusMeters: Number(searchResult.radius_m),
  };
}

export function searchAreaBounds(center, radiusMeters) {
  if (!Array.isArray(center) || center.length !== 2 || !center.every(Number.isFinite) || !Number.isFinite(radiusMeters) || radiusMeters <= 0) return null;
  const latitudeDelta = radiusMeters / 111320;
  const longitudeDelta = radiusMeters / (111320 * Math.max(Math.abs(Math.cos(center[0] * Math.PI / 180)), 0.01));
  return [[center[0] - latitudeDelta, center[1] - longitudeDelta], [center[0] + latitudeDelta, center[1] + longitudeDelta]];
}

export const BUSINESS_PROVIDER_LABELS = {
  openstreetmap: "OpenStreetMap", playwright: "Browser Search",
  geoapify: "Geoapify", google: "Google Places",
};

export const PEOPLE_PROVIDER_LABELS = {
  official_website: "Official Website", apollo: "Apollo", zoominfo: "ZoomInfo",
};

export function availableProviders(settings, group = "business") {
  const ids = group === "business" ? settings?.business_providers : settings?.people_providers;
  const labels = group === "business" ? BUSINESS_PROVIDER_LABELS : PEOPLE_PROVIDER_LABELS;
  return (ids || []).filter((id) => settings?.providers?.[id]?.configured).map((id) => ({ id, name: labels[id] || id }));
}

export function providerStatus(settings, id) {
  const enabled = [...(settings?.business_providers || []), ...(settings?.people_providers || [])].includes(id);
  return { enabled, configured: Boolean(settings?.providers?.[id]?.configured), usable: enabled && Boolean(settings?.providers?.[id]?.configured) };
}

export function dataCoverage(businesses) {
  const fields = ["address", "phone", "email", "website", "brand"];
  const total = businesses.length;
  return fields.map((field) => {
    const count = businesses.filter((item) => Boolean(item?.[field])).length;
    return { field, label: field[0].toUpperCase() + field.slice(1), count, percentage: total ? Math.round((count / total) * 100) : 0 };
  });
}

export function contactStatus(business) {
  if (business?.enrichment_status === "FOUND" || (business?.phone && business?.email)) return "Enriched";
  if (business?.phone || business?.email || business?.website) return "Partial";
  return "Not enriched";
}

export function toggleSelection(selected, id) {
  return selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id];
}

export function mergeBusinesses(current, updated) {
  return current.map((item) => updated.find((candidate) => candidate.id === item.id) || item);
}

export function providerSources(business) {
  const values = Array.isArray(business?.sources) ? business.sources : String(business?.source || "").split("+");
  return [...new Set(values.map((item) => String(item).trim()).filter(Boolean))];
}

export function enrichmentSummary(outcomes = []) {
  const counts = { enriched: 0, already_enriched: 0, skipped_no_website: 0, failed: 0 };
  outcomes.forEach((item) => { if (Object.hasOwn(counts, item?.status)) counts[item.status] += 1; });
  return `Enrichment complete: ${counts.enriched} enriched, ${counts.already_enriched} already enriched, ${counts.skipped_no_website} skipped — no website, ${counts.failed} failed.`;
}

export function operationLabel(operation, form = {}) {
  if (operation === "search") {
    const browser = form.providers?.includes("playwright");
    const depth = browser ? `${String(form.search_depth || "standard").replace(/^./, (value) => value.toUpperCase())} depth` : "Selected providers";
    const duration = { quick: "Up to ~30 sec", standard: "Up to ~2 min", deep: "Up to ~4 min", maximum: "Up to ~6 min" }[form.search_depth];
    return { title: "Searching businesses...", detail: browser ? `Browser Search · ${depth} · ${duration}` : depth };
  }
  return {
    enrich: { title: "Enriching selected businesses...", detail: "Checking official public websites" },
    people: { title: "Finding decision makers...", detail: "Using selected people providers" },
    preview: { title: "Checking CRM duplicates...", detail: "Preparing Lead import preview" },
    import: { title: "Saving confirmed WhatsApp contacts...", detail: "No messages or workflows will be started" },
  }[operation] || null;
}

export function validateCoordinates(latitude, longitude) {
  const latitudeText = String(latitude ?? "").trim();
  const longitudeText = String(longitude ?? "").trim();
  const errors = {};
  if (!latitudeText && !longitudeText) return { errors, valid: false, empty: true };
  if (!latitudeText) errors.latitude = "Enter latitude when longitude is provided.";
  if (!longitudeText) errors.longitude = "Enter longitude when latitude is provided.";
  const lat = Number(latitudeText); const lng = Number(longitudeText);
  if (latitudeText && !Number.isFinite(lat)) errors.latitude = "Enter a valid numeric latitude.";
  else if (latitudeText && (lat < -90 || lat > 90)) errors.latitude = "Latitude must be between -90 and 90.";
  if (longitudeText && !Number.isFinite(lng)) errors.longitude = "Enter a valid numeric longitude.";
  else if (longitudeText && (lng < -180 || lng > 180)) errors.longitude = "Longitude must be between -180 and 180.";
  return { errors, valid: Object.keys(errors).length === 0, empty: false, latitude: lat, longitude: lng };
}

export function resolveSearchCenter(location, coordinates) {
  const manual = validateCoordinates(coordinates?.latitude, coordinates?.longitude);
  if (coordinates?.manuallyEdited && manual.valid) {
    return { latitude: manual.latitude, longitude: manual.longitude, locationName: coordinates.locationName || "Custom coordinates", source: "manual" };
  }
  if (location && Number.isFinite(Number(location.latitude)) && Number.isFinite(Number(location.longitude))) {
    return { latitude: Number(location.latitude), longitude: Number(location.longitude), locationName: location.display_name, source: "location" };
  }
  if (manual.valid) return { latitude: manual.latitude, longitude: manual.longitude, locationName: coordinates?.locationName || "Custom coordinates", source: "manual" };
  return null;
}

export function buildSearchPayload(form, location, coordinates) {
  const center = resolveSearchCenter(location, coordinates);
  if (!center) return null;
  return {
    location_name: center.locationName, latitude: center.latitude, longitude: center.longitude,
    radius_m: form.radius_m, category: form.category, providers: form.providers,
    search_depth: form.search_depth,
  };
}
