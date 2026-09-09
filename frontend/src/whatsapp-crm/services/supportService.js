import apiClient from "../../shared/services/apiClient.js";

export async function getTags() {
  const response = await apiClient.get("/tags/");
  return response.data;
}

export async function createTag(tag) {
  const response = await apiClient.post("/tags/", tag);
  return response.data;
}

export async function updateTag(tagId, tag) {
  const response = await apiClient.patch(`/tags/${tagId}/`, tag);
  return response.data;
}

export async function deleteTag(tagId) {
  await apiClient.delete(`/tags/${tagId}/`);
}

export async function getContactNotes(contactId) {
  const response = await apiClient.get(`/contacts/${contactId}/notes/`);
  return response.data;
}

export async function createContactNote(contactId, note) {
  const response = await apiClient.post(`/contacts/${contactId}/notes/`, { note });
  return response.data;
}

export async function updateContactTags(contactId, tagIds) {
  const response = await apiClient.patch(`/contacts/${contactId}/tags/`, { tag_ids: tagIds });
  return response.data;
}

export async function getConversationNotes(conversationId) {
  const response = await apiClient.get(`/conversations/${conversationId}/notes/`);
  return response.data;
}

export async function createConversationNote(conversationId, note) {
  const response = await apiClient.post(`/conversations/${conversationId}/notes/`, { note });
  return response.data;
}

export async function assignConversation(conversationId, assignedTo) {
  const response = await apiClient.patch(`/conversations/${conversationId}/assign/`, {
    assigned_to: assignedTo,
  });
  return response.data;
}

export async function updateConversationStatus(conversationId, status) {
  const response = await apiClient.patch(`/conversations/${conversationId}/status/`, { status });
  return response.data;
}
