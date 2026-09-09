import { useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, Database, Globe2, KeyRound, Search } from "lucide-react";

import { getCollectorProviders, updateCollectorProviders } from "../services/leadCollectorService.js";
import { SettingsCard, SettingsGrid, SettingsSection } from "../../shared/components/settings/SettingsLayout.jsx";

const businessProviders = [
  { id: "openstreetmap", name: "OpenStreetMap", description: "Keyless OpenStreetMap and Overpass business discovery.", icon: Globe2 },
  { id: "playwright", name: "Browser Search", description: "Browser-backed discovery with Quick, Standard, Deep, and Maximum coverage.", icon: Search },
  { id: "geoapify", name: "Geoapify", description: "Optional commercial places provider.", credential: "geoapify_api_key", icon: Database },
  { id: "google", name: "Google Places", description: "Optional Google Places API provider.", credential: "google_api_key", icon: Database },
];

const peopleProviders = [
  { id: "official_website", name: "Official Website", description: "Keyless public website, social profile, and decision-maker enrichment.", icon: Globe2 },
  { id: "apollo", name: "Apollo", description: "Optional people enrichment through your Apollo account.", credential: "apollo_api_key", icon: KeyRound },
  { id: "zoominfo", name: "ZoomInfo", description: "Optional people enrichment through your ZoomInfo account.", credential: "zoominfo_api_key", icon: KeyRound },
];

const emptyKeys = { google_api_key: "", geoapify_api_key: "", apollo_api_key: "", zoominfo_api_key: "" };

function ProviderCard({ provider, enabled, status, value, onToggle, onKeyChange }) {
  const Icon = provider.icon;
  const requiresKey = Boolean(status?.requires_key ?? provider.credential);
  const configured = requiresKey ? Boolean(status?.configured) : true;
  const statusLabel = requiresKey ? (configured ? "Configured" : "Not configured") : "Ready";
  return <article className={enabled ? "collector-provider collector-provider--enabled" : "collector-provider"}>
    <div className="collector-provider__heading"><span className="collector-provider__icon"><Icon size={18}/></span><div><h3>{provider.name}</h3><p>{provider.description}</p></div><label className="provider-switch"><input checked={enabled} onChange={onToggle} type="checkbox"/><span/></label></div>
    <div className={configured ? "provider-status provider-status--ready" : "provider-status"}>
      {configured ? <CheckCircle2 size={14}/> : <CircleAlert size={14}/>} <span>{statusLabel}</span>
      {!requiresKey && <small>No API key required</small>}
    </div>
    {requiresKey && provider.credential && <label className="provider-key">API Key<input autoComplete="off" onChange={(event) => onKeyChange(provider.credential, event.target.value)} placeholder={configured ? "Leave blank to keep saved key" : "Enter API key"} type="password" value={value}/></label>}
  </article>;
}

function LeadCollectorSettings() {
  const [settings, setSettings] = useState(null); const [keys, setKeys] = useState(emptyKeys);
  const [saving, setSaving] = useState(false); const [message, setMessage] = useState(""); const [error, setError] = useState("");

  useEffect(() => { getCollectorProviders().then(setSettings).catch(() => setError("Unable to load Lead Collector settings.")); }, []);
  function toggle(group, id) { setSettings((current) => ({ ...current, [group]: current[group].includes(id) ? current[group].filter((item) => item !== id) : [...current[group], id] })); }

  async function save(event) {
    event.preventDefault(); setSaving(true); setMessage(""); setError("");
    try {
      const updated = await updateCollectorProviders({ business_providers: settings.business_providers, people_providers: settings.people_providers, ...keys });
      setSettings(updated); setKeys(emptyKeys); setMessage("Lead Collector provider settings saved.");
    } catch (requestError) { setError(requestError.response?.data?.detail || "Unable to save Lead Collector settings."); }
    finally { setSaving(false); }
  }

  if (!settings) return <SettingsCard><p>{error || "Loading Lead Collector settings…"}</p></SettingsCard>;
  return <section className="settings-embedded-page lead-collector-settings"><SettingsSection>
    <form onSubmit={save}>
      <SettingsCard className="settings-card--primary"><div className="settings-card__header"><div><h2>Lead Collector providers</h2><p>Choose organization-wide discovery and enrichment providers. Saved credentials are encrypted and never returned by the API.</p></div></div>
        <h3 className="provider-section-title">Business Data Providers</h3><SettingsGrid className="provider-settings-grid">{businessProviders.map((provider) => <ProviderCard key={provider.id} provider={provider} enabled={settings.business_providers.includes(provider.id)} status={settings.providers?.[provider.id]} value={keys[provider.credential] || ""} onToggle={() => toggle("business_providers", provider.id)} onKeyChange={(field, value) => setKeys((current) => ({ ...current, [field]: value }))}/>)}</SettingsGrid>
        <h3 className="provider-section-title">Enrichment / People Providers</h3><SettingsGrid className="provider-settings-grid">{peopleProviders.map((provider) => <ProviderCard key={provider.id} provider={provider} enabled={settings.people_providers.includes(provider.id)} status={settings.providers?.[provider.id]} value={keys[provider.credential] || ""} onToggle={() => toggle("people_providers", provider.id)} onKeyChange={(field, value) => setKeys((current) => ({ ...current, [field]: value }))}/>)}</SettingsGrid>
        {message && <p className="form-success">{message}</p>}{error && <p className="form-error">{error}</p>}
        <div className="actions"><button className="button button--primary" disabled={saving || !settings.business_providers.length} type="submit">{saving ? "Saving…" : "Save Provider Settings"}</button></div>
      </SettingsCard>
    </form>
  </SettingsSection></section>;
}

export default LeadCollectorSettings;
