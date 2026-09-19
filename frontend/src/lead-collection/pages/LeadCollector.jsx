import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, MapPin, Search, Settings2, X } from "lucide-react";
import "leaflet/dist/leaflet.css";

import {
  createCollectorSearch, downloadCollectorExport, enrichBusinesses, exportErrorMessage, findDecisionMakers,
  getCollectorCategories, getCollectorProviders,
  importWhatsAppContacts, previewWhatsAppContacts, searchLocations,
} from "../services/leadCollectorService.js";
import {
  ADVANCED_SEARCH_DEFAULT_OPEN, availableProviders, buildSearchPayload,
  coordinatesFromLocation, coordinatesFromMap, enrichmentSummary, isLatestLocationRequest, mergeBusinesses, operationLabel, providerStatus, resolveSearchCenter,
  shouldSearchLocation, toggleSelection, validateCoordinates,
} from "../utils/leadCollectorHelpers.js";
import {
  BusinessDetailsDrawer, BusinessResultsTable, EmptyResults,
  ResultOverview, ResultsToolbar,
} from "../components/LeadCollectorResults.jsx";
import LeadCollectorMap from "../components/LeadCollectorMap.jsx";
import "./LeadCollector.css";

const depths = [
  ["quick", "Quick", "Up to ~30 sec"], ["standard", "Standard", "Up to ~2 min"],
  ["deep", "Deep", "Up to ~4 min"], ["maximum", "Maximum", "Up to ~6 min"],
];

function LeadCollector() {
  const [categories, setCategories] = useState([]); const [providerInfo, setProviderInfo] = useState(null);
  const [locationQuery, setLocationQuery] = useState(""); const [locations, setLocations] = useState([]); const [location, setLocation] = useState(null);
  const [coordinates, setCoordinates] = useState({ latitude: "", longitude: "", manuallyEdited: false }); const [coordinateErrors, setCoordinateErrors] = useState({});
  const [form, setForm] = useState({ category: "hotels_resorts", radius_m: 5000, providers: [], search_depth: "standard", people_providers: [] });
  const [businesses, setBusinesses] = useState([]); const [selected, setSelected] = useState([]); const [detail, setDetail] = useState(null);
  const [operation, setOperation] = useState(null); const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [searchResult, setSearchResult] = useState(null);
  const [exporting, setExporting] = useState(null);
  const [advancedOpen, setAdvancedOpen] = useState(ADVANCED_SEARCH_DEFAULT_OPEN); const [importOpen, setImportOpen] = useState(false); const [preview, setPreview] = useState([]);
  const [pickMode, setPickMode] = useState(false);
  const [detailTrigger, setDetailTrigger] = useState(null);
  const locationRequestId = useRef(0); const locationQueryRef = useRef("");

  useEffect(() => { Promise.all([getCollectorCategories(), getCollectorProviders()]).then(([categoryData, settings]) => { const business = availableProviders(settings); const people = availableProviders(settings, "people"); setCategories(categoryData); setProviderInfo(settings); setForm((current) => ({ ...current, providers: business.map((item) => item.id), people_providers: people.map((item) => item.id) })); }).catch((requestError) => setError(requestError.response?.data?.detail || "Could not load Lead Collector.")); }, []);
  useEffect(() => { locationQueryRef.current = locationQuery; const query = locationQuery.trim(); if (!shouldSearchLocation(query) || location?.display_name === locationQuery) { locationRequestId.current += 1; setLocations([]); return undefined; } const controller = new AbortController(); const requestId = ++locationRequestId.current; const timer = setTimeout(() => searchLocations(query, { signal: controller.signal }).then((results) => { if (isLatestLocationRequest(requestId, locationRequestId.current, query, locationQueryRef.current)) setLocations(results); }).catch((requestError) => { if (requestError.code !== "ERR_CANCELED" && isLatestLocationRequest(requestId, locationRequestId.current, query, locationQueryRef.current)) setLocations([]); }), 350); return () => { clearTimeout(timer); controller.abort(); }; }, [locationQuery, location]);

  const businessProviderOptions = useMemo(() => availableProviders(providerInfo), [providerInfo]);
  const peopleProviderOptions = useMemo(() => availableProviders(providerInfo, "people"), [providerInfo]);
  const categoryName = categories.find((item) => item.id === form.category)?.name || "Businesses";
  const searchCenter = resolveSearchCenter(location, coordinates);
  const selectedProviderNames = businessProviderOptions.filter((provider) => form.providers.includes(provider.id)).map((provider) => provider.name).join(" + ");
  const loading = Boolean(operation); const operationStatus = operationLabel(operation, form);

  function toggleProvider(group, id) { setForm((current) => ({ ...current, [group]: toggleSelection(current[group], id) })); }
  function updateBusinesses(updated) { setBusinesses((current) => mergeBusinesses(current, updated)); setDetail((current) => current ? updated.find((item) => item.id === current.id) || current : null); }
  function selectLocation(item) { setLocation(item); setLocationQuery(item.display_name); setLocations([]); setCoordinates(coordinatesFromLocation(item)); setCoordinateErrors({}); }
  function updateLocationQuery(value) { setLocationQuery(value); setLocation(null); setCoordinates((current) => current.manuallyEdited ? current : { latitude: "", longitude: "", manuallyEdited: false }); }
  function updateCoordinate(field, value) { setCoordinates((current) => ({ ...current, [field]: value, manuallyEdited: true, locationName: "Custom coordinates" })); setCoordinateErrors((current) => ({ ...current, [field]: undefined })); }
  function pickMapLocation(latitude, longitude) { setLocation(null); setLocationQuery("Custom map location"); setCoordinates(coordinatesFromMap(latitude, longitude)); setCoordinateErrors({}); setPickMode(false); }

  async function runSearch(event) {
    event.preventDefault(); setError(""); setMessage("");
    const coordinateValidation = validateCoordinates(coordinates.latitude, coordinates.longitude);
    if (coordinates.manuallyEdited && !coordinateValidation.valid) { setCoordinateErrors(coordinateValidation.errors); setError("Enter a valid latitude and longitude pair."); return; }
    const searchPayload = buildSearchPayload(form, location, coordinates);
    if (!searchPayload) { setCoordinateErrors(coordinateValidation.errors); setError("Choose a location or enter valid exact coordinates."); return; }
    if (!form.providers.length) { setError("Select at least one enabled business data provider."); return; }
    if (form.providers.some((id) => !providerStatus(providerInfo, id).usable)) { setError("A selected provider is no longer enabled or configured."); return; }
    setOperation("search"); setBusinesses([]); setSelected([]); setSearchResult(null);
    try { const result = await createCollectorSearch(searchPayload); setSearchResult(result); setBusinesses(result.businesses || []); }
    catch (requestError) { setError(requestError.response?.data?.detail || requestError.response?.data?.error || "Business discovery failed."); }
    finally { setOperation(null); }
  }

  async function runEnrichment() { setOperation("enrich"); setError(""); try { const result = await enrichBusinesses(selected, searchResult.id); updateBusinesses(result.businesses); setMessage(enrichmentSummary(result.outcomes)); } catch { setError("Public website enrichment could not be completed. Try again or select fewer businesses."); } finally { setOperation(null); } }
  async function runDecisionMakers() { setOperation("people"); setError(""); try { const updated = await findDecisionMakers(selected, form.people_providers, searchResult.id); updateBusinesses(updated); const failed = updated.filter((item) => item.decision_maker_status === "ERROR").length; setMessage(failed ? `Decision-maker search completed with ${failed} failure${failed === 1 ? "" : "s"}.` : "Decision-maker search completed."); } catch (requestError) { setError(requestError.response?.data?.detail || "Decision-maker search could not be completed."); } finally { setOperation(null); } }
  async function openImport() { setOperation("preview"); setError(""); try { setPreview(await previewWhatsAppContacts(selected, searchResult.id)); setImportOpen(true); } catch { setError("Could not check CRM contact duplicates. Please try again."); } finally { setOperation(null); } }
  async function confirmImport() { setOperation("import"); try { const outcomes = await importWhatsAppContacts(selected, searchResult.id); setPreview(outcomes); const count = (status) => outcomes.filter((item) => item.status === status).length; setMessage(`WhatsApp contacts imported: ${count("created")} created, ${count("already_exists")} already existed, ${count("category_updated")} category updated, ${count("skipped_no_confirmed_whatsapp")} skipped — no confirmed WhatsApp number.`); } catch (requestError) { setError(requestError.response?.data?.detail || "WhatsApp contact import failed."); } finally { setOperation(null); } }
  async function exportResults(format) { if (exporting) return; const ids = selected.length ? selected : businesses.map((item) => item.id); setExporting(format); setError(""); try { await downloadCollectorExport(format, ids, searchResult); setMessage(`${format.toUpperCase()} export prepared.`); } catch (requestError) { setError(await exportErrorMessage(requestError, format)); } finally { setExporting(null); } }

  return <main className="collector-page collector-page--workspace">
    <header className="collector-header"><div><span>Growth tools</span><h1>Lead Collector</h1><p>Discover public business information, enrich selected results, find decision-makers, export results, and save confirmed public WhatsApp contacts to CRM Contacts.</p></div></header>
    <section className="collector-search-panel panel"><div className="collector-section-heading"><div><span>Business discovery</span><h2>Search Businesses</h2><p>Search an airport, city, or area, then choose your business type and coverage.</p></div></div>
      <div className="location-search-row"><label className="collector-location"><span>Location search</span><div><Search size={16}/><input value={locationQuery} onChange={(event) => updateLocationQuery(event.target.value)} placeholder="Search airport, city, or location…"/></div>{locations.length > 0 && <div className="location-results">{locations.map((item) => <button type="button" key={item.provider_id || `${item.latitude}-${item.longitude}`} onClick={() => selectLocation(item)}><MapPin size={15}/><span><strong>{item.name || item.display_name}</strong><small>{item.secondary_name || item.display_name}</small></span></button>)}</div>}</label><button className="button" disabled={locationQuery.trim().length < 3} type="button" onClick={() => searchLocations(locationQuery).then(setLocations)}>Search</button></div>
      <form onSubmit={runSearch}>
        <button className="advanced-search-toggle" aria-expanded={advancedOpen} type="button" onClick={() => setAdvancedOpen((value) => !value)}><Settings2 size={14}/>Advanced Search<ChevronDown className={advancedOpen ? "rotated" : ""} size={14}/></button>{advancedOpen && <div className="coordinate-search"><div><label>Latitude<input inputMode="decimal" onChange={(event) => updateCoordinate("latitude", event.target.value)} placeholder="12.993374" value={coordinates.latitude}/></label>{coordinateErrors.latitude && <small className="coordinate-error">{coordinateErrors.latitude}</small>}</div><div><label>Longitude<input inputMode="decimal" onChange={(event) => updateCoordinate("longitude", event.target.value)} placeholder="80.172587" value={coordinates.longitude}/></label>{coordinateErrors.longitude && <small className="coordinate-error">{coordinateErrors.longitude}</small>}</div><p>Search a location above or enter exact coordinates manually. Manually edited coordinates take priority.</p></div>}
        <div className="primary-search-controls"><div className="selected-location"><MapPin size={15}/><div><small>Search center</small><strong title={resolveSearchCenter(location, coordinates)?.locationName}>{resolveSearchCenter(location, coordinates)?.locationName || "Choose a location or enter coordinates"}</strong></div></div><label>Business Type<select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Radius<select value={form.radius_m} onChange={(event) => setForm({ ...form, radius_m: Number(event.target.value) })}>{[1000, 2000, 3000, 5000, 10000, 15000, 20000].map((value) => <option key={value} value={value}>{value / 1000} km</option>)}</select></label><button className="button button--primary find-businesses" disabled={loading || !resolveSearchCenter(location, coordinates) || !form.providers.length}><Search size={16}/>{loading ? "Working…" : "Find Businesses"}</button></div>
        <div className="provider-groups"><div className="provider-line"><strong>Providers</strong>{businessProviderOptions.length ? businessProviderOptions.map((provider) => <label className="provider-choice" key={provider.id}><input checked={form.providers.includes(provider.id)} disabled={loading} onChange={() => toggleProvider("providers", provider.id)} type="checkbox"/><span>{provider.name}</span></label>) : <small>No providers configured in Settings.</small>}</div><div className="provider-line"><strong>Decision Makers</strong>{peopleProviderOptions.length ? peopleProviderOptions.map((provider) => <label className="provider-choice" key={provider.id}><input checked={form.people_providers.includes(provider.id)} disabled={loading} onChange={() => toggleProvider("people_providers", provider.id)} type="checkbox"/><span>{provider.name}</span></label>) : <small>No providers configured.</small>}</div></div>
        {form.providers.includes("playwright") && <div className="search-depth-section"><div><strong>Search Depth</strong><small>Server-controlled Browser Search coverage</small></div><div className="depth-options">{depths.map(([id, name, duration]) => <label className={form.search_depth === id ? "depth-option depth-option--active" : "depth-option"} key={id}><input checked={form.search_depth === id} name="depth" onChange={() => setForm({ ...form, search_depth: id })} type="radio"/><strong>{name}</strong><span>{duration}</span></label>)}</div></div>}
      </form>
    </section>
    <section className="collector-area-overview"><div className="collector-search-map panel"><div className="collector-map-toolbar"><div><span>Search Area</span><strong title={searchCenter?.locationName}>{searchCenter?.locationName || "Choose a location or pick a point"}</strong><small>{searchCenter ? `${searchCenter.latitude.toFixed(5)}, ${searchCenter.longitude.toFixed(5)} · ${form.radius_m / 1000} km` : "Global map · no search center selected"}</small></div><button className={pickMode ? "button button--primary" : "button"} type="button" onClick={() => setPickMode((value) => !value)}>{pickMode ? "Cancel picking" : "Pick from map"}</button></div><LeadCollectorMap businesses={businesses} center={searchCenter ? [searchCenter.latitude, searchCenter.longitude] : null} centerLabel={searchCenter?.locationName || ""} onBusinessClick={(item, trigger) => { setDetailTrigger(trigger); setDetail(item); }} onPick={pickMapLocation} pickMode={pickMode} radiusMeters={form.radius_m}/>{pickMode && <p className="map-pick-help">Click anywhere on the map to set the exact search center.</p>}</div><ResultOverview businesses={businesses} categoryName={categoryName} centerLabel={searchCenter?.locationName} providerNames={selectedProviderNames} radiusMeters={form.radius_m} searchDepth={form.providers.includes("playwright") ? `${depths.find(([id]) => id === form.search_depth)?.[1]} · ${depths.find(([id]) => id === form.search_depth)?.[2]}` : null} searchResult={searchResult}/></section>
    {operationStatus && <div aria-live="polite" className="collector-loading" role="status"><span className="collector-loading__bar"/><Search aria-hidden="true" size={18}/><div><strong>{operationStatus.title}</strong><small>{operationStatus.detail}</small></div></div>}
    {error && <p aria-live="assertive" className="collector-alert collector-alert--error" role="alert">{error}</p>}{message && <p aria-live="polite" className="collector-alert collector-alert--success" role="status">{message}</p>}
    {businesses.length > 0 ? <><ResultsToolbar businesses={businesses} categoryName={categoryName} canFindPeople={form.people_providers.length > 0} exporting={exporting} loading={loading} operation={operation} selected={selected} onClear={() => setSelected([])} onEnrich={runEnrichment} onExport={exportResults} onFindPeople={runDecisionMakers} onImport={openImport} onSelectAll={() => setSelected(businesses.map((item) => item.id))}/><BusinessResultsTable businesses={businesses} onToggle={(id) => setSelected((current) => toggleSelection(current, id))} onView={(item, trigger) => { setDetailTrigger(trigger); setDetail(item); }} selected={selected}/></> : <EmptyResults loading={loading} searched={Boolean(searchResult)}/>} 
    <BusinessDetailsDrawer business={detail} onClose={() => setDetail(null)} returnFocus={detailTrigger}/>
    {importOpen && <div className="collector-modal"><button aria-label="Close contact import preview" className="collector-modal__scrim" onClick={() => setImportOpen(false)}/><section><button aria-label="Close contact import preview" className="collector-modal__close" onClick={() => setImportOpen(false)}><X/></button><span className="modal-kicker">CRM contact import</span><h2>Add WhatsApp Contacts</h2><p>Only confirmed public WhatsApp evidence is eligible. Saving contacts never sends messages or starts workflows.</p><div className="import-preview">{preview.map((row, index) => <div key={`${row.business_id}-${row.number || index}`}><span><strong>{row.name || `Business ${row.business_id}`}</strong><small>{row.number || "No confirmed WhatsApp number"}{row.category ? ` · ${row.category}` : ""}</small></span><em className={["ready", "created", "category_updated"].includes(row.status) ? "import-ready" : ""}>{row.status?.replaceAll("_", " ")}</em></div>)}</div><div className="actions"><button className="button button--primary" disabled={loading || !preview.some((row) => row.status === "ready")} onClick={confirmImport}>{operation === "import" ? "Adding WhatsApp Contacts..." : `Add ${preview.filter((row) => row.status === "ready").length} WhatsApp Contacts`}</button><button className="button" onClick={() => setImportOpen(false)}>Cancel</button></div></section></div>}
  </main>;
}

export default LeadCollector;
