import axios from "axios";

import { notify } from "./notificationService.js";
import { clearTokens, getRefreshToken, saveAccessToken, saveTokens } from "./tokenStorage.js";

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000/api";
let refreshPromise = null;

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 5000,
});

export const refreshClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 5000,
});

function isAuthEndpoint(url = "") {
  return (
    url.includes("/auth/login/") ||
    url.includes("/auth/register/") ||
    url.includes("/auth/logout/") ||
    url.includes("/auth/token/refresh/")
  );
}

function handleSessionExpired() {
  clearTokens();
  notify("warning", "Session expired", "Your session has expired. Please log in again.");

  if (window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

async function refreshAccessToken() {
  if (!refreshPromise) {
    const refresh = getRefreshToken();

    if (!refresh) {
      handleSessionExpired();
      return Promise.reject(new Error("Missing refresh token."));
    }

    refreshPromise = refreshClient
      .post("/auth/token/refresh/", { refresh })
      .then((response) => {
        const { access, refresh: nextRefresh } = response.data;
        if (!access) {
          throw new Error("Refresh response did not include an access token.");
        }

        if (nextRefresh) {
          saveTokens({ access, refresh: nextRefresh });
        } else {
          saveAccessToken(access);
        }

        return access;
      })
      .catch((error) => {
        handleSessionExpired();
        throw error;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

apiClient.interceptors.request.use((config) => {
  const headers = axios.AxiosHeaders.from(config.headers || {});

  const token = localStorage.getItem("whatsapp_crm_access_token");

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  config.headers = headers;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthEndpoint(originalRequest.url)
    ) {
      originalRequest._retry = true;
      try {
        const access = await refreshAccessToken();
        const headers = axios.AxiosHeaders.from(originalRequest.headers || {});
        headers.set("Authorization", `Bearer ${access}`);
        originalRequest.headers = headers;
        return apiClient(originalRequest);
      } catch {
        return Promise.reject(error);
      }
    }

    if (error.response?.status === 403) {
      notify("warning", "Permission denied", error.response.data?.detail || "Your role cannot perform that action.");
    }
    if (error.response?.status >= 500) {
      notify("error", "Server error", "Something went wrong on the server.");
    }
    return Promise.reject(error);
  },
);

export default apiClient;
