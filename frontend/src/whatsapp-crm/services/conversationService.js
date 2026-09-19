import apiClient from "../../shared/services/apiClient.js";

export async function getConversations(filters = {}) {
  const response = await apiClient.get("/conversations/", { params: filters });
  return response.data;
}

export async function getConversation(conversationId) {
  const response = await apiClient.get(`/conversations/${conversationId}/`);
  return response.data;
}

export async function updateConversation(conversationId, data) {
  const response = await apiClient.patch(`/conversations/${conversationId}/`, data);
  return response.data;
}

export async function getMessages(conversationId) {
  const response = await apiClient.get(`/conversations/${conversationId}/messages/`);
  return response.data;
}

export async function createMessage(conversationId, data) {
  const response = await apiClient.post(`/conversations/${conversationId}/messages/`, data);
  return response.data;
}

export async function uploadMediaMessage(conversationId, formData, onUploadProgress) {
  const response = await apiClient.post(`/conversations/${conversationId}/messages/media/`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 60000,
    onUploadProgress,
  });
  return response.data;
}
