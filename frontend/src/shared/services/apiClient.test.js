import assert from "node:assert/strict";
import test from "node:test";
import axios from "axios";

const stored = new Map();
globalThis.localStorage = { getItem: (key) => stored.get(key) || null, setItem: (key, value) => stored.set(key, value), removeItem: (key) => stored.delete(key) };
globalThis.CustomEvent = class CustomEvent { constructor(type, options) { this.type = type; this.detail = options?.detail; } };
globalThis.window = { dispatchEvent() {}, location: { pathname: "/lead-collector", assign(path) { this.assigned = path; } } };

const { default: apiClient, refreshClient } = await import("./apiClient.js");

function unauthorized(config) {
  return Promise.reject(new axios.AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, { status: 401, data: { detail: "Token is invalid or expired" }, headers: {}, config }));
}

test("shared client refreshes once, retries concurrent requests, and applies the new Bearer token", async () => {
  stored.set("whatsapp_crm_access_token", "expired-access"); stored.set("whatsapp_crm_refresh_token", "valid-refresh");
  let refreshes = 0; const attempts = new Map(); const retriedHeaders = [];
  refreshClient.defaults.adapter = async (config) => { refreshes += 1; assert.deepEqual(JSON.parse(config.data), { refresh: "valid-refresh" }); return { status: 200, statusText: "OK", headers: {}, config, data: { access: "fresh-access" } }; };
  apiClient.defaults.adapter = async (config) => {
    const key = config.params.q; const count = (attempts.get(key) || 0) + 1; attempts.set(key, count);
    if (count === 1) return unauthorized(config);
    retriedHeaders.push(config.headers.get("Authorization"));
    return { status: 200, statusText: "OK", headers: {}, config, data: { results: [key] } };
  };
  const responses = await Promise.all([apiClient.get("/lead-collector/locations/", { params: { q: "vij" } }), apiClient.get("/lead-collector/locations/", { params: { q: "vijayawada" } })]);
  assert.equal(refreshes, 1); assert.deepEqual(responses.map((item) => item.data.results[0]), ["vij", "vijayawada"]); assert.deepEqual(retriedHeaders, ["Bearer fresh-access", "Bearer fresh-access"]); assert.equal(stored.get("whatsapp_crm_access_token"), "fresh-access");
});

test("failed refresh preserves the shared session-expired behavior", async () => {
  stored.set("whatsapp_crm_access_token", "expired-again"); stored.set("whatsapp_crm_refresh_token", "invalid-refresh"); window.location.assigned = null;
  refreshClient.defaults.adapter = (config) => unauthorized(config);
  apiClient.defaults.adapter = (config) => unauthorized(config);
  await assert.rejects(apiClient.get("/lead-collector/locations/", { params: { q: "vijayawada" } }));
  assert.equal(stored.has("whatsapp_crm_access_token"), false); assert.equal(stored.has("whatsapp_crm_refresh_token"), false); assert.equal(window.location.assigned, "/login");
});
