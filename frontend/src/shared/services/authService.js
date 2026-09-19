import apiClient from "./apiClient.js";
import { clearTokens, getRefreshToken, saveTokens } from "./tokenStorage.js";

function storeAuthResponse(response) {
  saveTokens({
    access: response.data.access,
    refresh: response.data.refresh,
  });

  return response.data;
}

export async function register({ email, password }) {
  const response = await apiClient.post("/auth/register/", { email, password });
  return storeAuthResponse(response);
}

export async function login({ email, password }) {
  const response = await apiClient.post("/auth/login/", { email, password });
  return storeAuthResponse(response);
}

export async function getCurrentUser() {
  const response = await apiClient.get("/auth/me/");
  return response.data;
}

export async function logout() {
  const refresh = getRefreshToken();

  if (refresh) {
    await apiClient.post("/auth/logout/", { refresh });
  }

  clearTokens();
}
