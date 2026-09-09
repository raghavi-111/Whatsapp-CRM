import apiClient from "../../shared/services/apiClient.js";

export async function getTemplates(filters = {}) {
  const response = await apiClient.get("/templates/", { params: filters });
  return response.data;
}

export async function createTemplate(template) {
  const response = await apiClient.post("/templates/", template);
  return response.data;
}

export async function updateTemplate(templateId, template) {
  const response = await apiClient.patch(`/templates/${templateId}/`, template);
  return response.data;
}

export async function deleteTemplate(templateId) {
  await apiClient.delete(`/templates/${templateId}/`);
}

export async function sendTemplate(templateId, payload) {
  const response = await apiClient.post(`/templates/${templateId}/send/`, payload);
  return response.data;
}
