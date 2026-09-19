import apiClient from "../../shared/services/apiClient.js";

export async function getBroadcastCampaigns() {
  const response = await apiClient.get("/broadcasts/campaigns/");
  return response.data;
}

export async function createBroadcastCampaign(campaign) {
  const response = await apiClient.post("/broadcasts/campaigns/", campaign);
  return response.data;
}

export async function updateBroadcastCampaign(campaignId, campaign) {
  const response = await apiClient.patch(`/broadcasts/campaigns/${campaignId}/`, campaign);
  return response.data;
}

export async function estimateBroadcastRecipients(payload) {
  const response = await apiClient.post("/broadcasts/campaigns/estimate/", payload);
  return response.data;
}

export async function sendBroadcastNow(campaignId) {
  const response = await apiClient.post(`/broadcasts/campaigns/${campaignId}/send-now/`);
  return response.data;
}

export async function scheduleBroadcast(campaignId, scheduledAt) {
  const response = await apiClient.post(`/broadcasts/campaigns/${campaignId}/schedule/`, {
    scheduled_at: scheduledAt,
  });
  return response.data;
}

export async function cancelBroadcast(campaignId) {
  const response = await apiClient.post(`/broadcasts/campaigns/${campaignId}/cancel/`);
  return response.data;
}
