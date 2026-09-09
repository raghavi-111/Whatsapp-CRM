import apiClient from "../../shared/services/apiClient.js";

export async function getLeads(filters = {}) { return (await apiClient.get("/leads/", { params: filters })).data; }
export async function getLead(id) { return (await apiClient.get(`/leads/${id}/`)).data; }
export async function createLead(data) { return (await apiClient.post("/leads/", data)).data; }
export async function updateLead(id, data) { return (await apiClient.patch(`/leads/${id}/`, data)).data; }
export async function deleteLead(id) { await apiClient.delete(`/leads/${id}/`); }
export async function convertLead(id) { return (await apiClient.post(`/leads/${id}/convert/`)).data; }
export async function getServices(activeOnly = false) { return (await apiClient.get("/leads/services/", { params: activeOnly ? { active: true } : {} })).data; }
export async function createService(data) { return (await apiClient.post("/leads/services/", data)).data; }
export async function updateService(id, data) { return (await apiClient.patch(`/leads/services/${id}/`, data)).data; }
export async function getLeadAssignees() { return (await apiClient.get("/leads/assignees/")).data; }
