const ACCESS_TOKEN_KEY = "whatsapp_crm_access_token";
const REFRESH_TOKEN_KEY = "whatsapp_crm_refresh_token";
export const AUTH_TOKENS_CHANGED_EVENT = "whatsapp-crm-auth-tokens-changed";

function emitTokensChanged() {
  window.dispatchEvent(new Event(AUTH_TOKENS_CHANGED_EVENT));
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function saveTokens({ access, refresh }) {
  if (access) {
    localStorage.setItem(ACCESS_TOKEN_KEY, access);
  }
  if (refresh) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
  }
  emitTokensChanged();
}

export function saveAccessToken(access) {
  localStorage.setItem(ACCESS_TOKEN_KEY, access);
  emitTokensChanged();
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  emitTokensChanged();
}

export function isLoggedIn() {
  return Boolean(getAccessToken());
}
