import apiClient from "../../shared/services/apiClient.js";

export async function getContacts(filters = {}) {
  const response = await apiClient.get("/contacts/", { params: filters });
  return response.data;
}

export async function getContactCategories() {
  const response = await apiClient.get("/contacts/categories/");
  return response.data;
}

export async function createContact(contact) {
  const response = await apiClient.post("/contacts/", contact);
  return response.data;
}

export async function updateContact(contactId, contact) {
  const response = await apiClient.patch(`/contacts/${contactId}/`, contact);
  return response.data;
}

export async function deleteContact(contactId) {
  await apiClient.delete(`/contacts/${contactId}/`);
}

export async function startContactConversation(contactId) {
  const response = await apiClient.post(`/contacts/${contactId}/start-conversation/`);
  return response.data;
}

export async function uploadWhatsAppWorkbook(file) {
  const data = new FormData(); data.append("file", file);
  return (await apiClient.post("/contacts/whatsapp-import/workbook/", data)).data;
}
export async function inspectWhatsAppSheet(token, sheet) { return (await apiClient.post("/contacts/whatsapp-import/sheet/", { token, sheet })).data; }
export async function previewWhatsAppWorkbook(options) { return (await apiClient.post("/contacts/whatsapp-import/preview/", options)).data; }
export async function commitWhatsAppWorkbook(options) { return (await apiClient.post("/contacts/whatsapp-import/commit/", options)).data; }
