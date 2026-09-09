import apiClient from "../../shared/services/apiClient.js";

export async function getAnalyticsSummary() {
  const response = await apiClient.get("/analytics/summary/");
  return response.data;
}

export async function getMessagesAnalytics(days) {
  const response = await apiClient.get("/analytics/messages/", { params: days ? { days } : undefined });
  return response.data;
}

export async function getConversationsAnalytics() {
  const response = await apiClient.get("/analytics/conversations/");
  return response.data;
}

export async function getAgentsAnalytics() {
  const response = await apiClient.get("/analytics/agents/");
  return response.data;
}

export async function getAutomationsAnalytics() {
  const response = await apiClient.get("/analytics/automations/");
  return response.data;
}
