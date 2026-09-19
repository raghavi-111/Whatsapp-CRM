import apiClient from "../../shared/services/apiClient.js";

export async function searchLocations(q, options = {}) { return (await apiClient.get("/lead-collector/locations/", { params: { q }, signal: options.signal })).data.results; }
export async function getCollectorCategories() { return (await apiClient.get("/lead-collector/categories/")).data.categories; }
export async function getCollectorProviders() { return (await apiClient.get("/lead-collector/providers/")).data; }
export async function updateCollectorProviders(data) { return (await apiClient.patch("/lead-collector/providers/", data)).data; }
export async function createCollectorSearch(data) { return (await apiClient.post("/lead-collector/searches/", data, { timeout: 380000 })).data; }
export async function enrichBusinesses(ids, searchId) { return (await apiClient.post("/lead-collector/businesses/enrich/", { business_ids: ids, search_id: searchId }, { timeout: 380000 })).data; }
export async function findDecisionMakers(ids, providers, searchId) { return (await apiClient.post("/lead-collector/businesses/decision-makers/", { business_ids: ids, providers, search_id: searchId }, { timeout: 380000 })).data.businesses; }
export async function previewLeadImport(ids, searchId) { return (await apiClient.post("/lead-collector/imports/preview/", { business_ids: ids, search_id: searchId })).data.results; }
export async function importCollectorLeads(ids, serviceId, searchId) { return (await apiClient.post("/lead-collector/imports/leads/", { business_ids: ids, service_id: Number(serviceId), search_id: searchId })).data.results; }
export async function previewWhatsAppContacts(ids, searchId) { return (await apiClient.post("/lead-collector/imports/whatsapp-contacts/preview/", { business_ids: ids, search_id: searchId })).data.results; }
export async function importWhatsAppContacts(ids, searchId) { return (await apiClient.post("/lead-collector/imports/whatsapp-contacts/", { business_ids: ids, search_id: searchId })).data.results; }

export async function downloadCollectorExport(format, ids, context) {
  const exportContext = context ? Object.fromEntries(Object.entries(context).filter(([key]) => key !== "businesses")) : {};
  const response = await apiClient.post(`/lead-collector/exports/${format}/`, { business_ids: ids, context: exportContext }, { responseType: "blob", timeout: 380000 });
  const url = URL.createObjectURL(response.data);
  const disposition = response.headers?.["content-disposition"] || "";
  const headerName = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  const locationSlug = String(context?.location_name || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const fallback = `business-leads-${locationSlug ? `${locationSlug}-` : ""}${new Date().toISOString().slice(0, 10)}.${format === "excel" ? "xlsx" : "csv"}`;
  const link = document.createElement("a"); link.href = url; link.download = headerName || fallback; link.click();
  URL.revokeObjectURL(url);
}

export async function exportErrorMessage(error, format) {
  const fallback = `Could not export ${format.toUpperCase()}.`;
  const data = error.response?.data;
  if (!(data instanceof Blob) || !data.type?.includes("json")) return error.response?.data?.detail || fallback;
  try {
    const payload = JSON.parse(await data.text());
    if (payload/detail) return payload/detail;
    if (payload/business_ids) {
      const first = Array.isArray(payload.business_ids) ? payload.business_ids[0] : Object.values(payload.business_ids).flat()[0];
      return first || fallback;
    }
  } catch { return fallback; }
  return fallback;
}
