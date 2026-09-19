import apiClient from "../../shared/services/apiClient.js";

export async function getDeals(filters = {}) {
  const response = await apiClient.get("/pipelines/deals/", { params: filters });
  return response.data;
}

export async function createDeal(deal) {
  const response = await apiClient.post("/pipelines/deals/", deal);
  return response.data;
}

export async function updateDeal(dealId, deal) {
  const response = await apiClient.patch(`/pipelines/deals/${dealId}/`, deal);
  return response.data;
}
