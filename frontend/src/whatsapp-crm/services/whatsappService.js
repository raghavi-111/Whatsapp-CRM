import apiClient from "../../shared/services/apiClient.js";

export async function getWhatsAppConfig() {
  const response = await apiClient.get("/whatsapp/config/");
  return response.data;
}

export async function createWhatsAppConfig(config) {
  const response = await apiClient.post("/whatsapp/config/", config);
  return response.data;
}

export async function updateWhatsAppConfig(config) {
  const response = await apiClient.patch("/whatsapp/config/", config);
  return response.data;
}

export async function testWhatsAppConnection() {
  const response = await apiClient.post("/whatsapp/config/test-connection/");
  return response.data;
}
