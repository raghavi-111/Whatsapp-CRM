import apiClient from "../../shared/services/apiClient.js";

export async function getAutomations() {
  const response = await apiClient.get("/automations/");
  return response.data;
}

export async function createAutomation(rule) {
  const response = await apiClient.post("/automations/", rule);
  return response.data;
}

export async function updateAutomation(ruleId, rule) {
  const response = await apiClient.patch(`/automations/${ruleId}/`, rule);
  return response.data;
}

export async function deleteAutomation(ruleId) {
  await apiClient.delete(`/automations/${ruleId}/`);
}

export async function getAutomationLogs(filters = {}) {
  const response = await apiClient.get("/automations/logs/", { params: filters });
  return response.data;
}

export async function simulateInboundMessage(data) {
  const response = await apiClient.post("/whatsapp/simulate-inbound/", data);
  return response.data;
}

export async function getAutomationMedia() {
  return (await apiClient.get("/automations/media/")).data;
}

export async function uploadAutomationMedia(file, mediaType) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("media_type", mediaType);
  return (await apiClient.post("/automations/media/", formData, { headers: { "Content-Type": "multipart/form-data" } })).data;
}
