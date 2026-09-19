import assert from "node:assert/strict";
import test from "node:test";

globalThis.localStorage = { getItem: () => null, removeItem() {}, setItem() {} };
globalThis.CustomEvent = class CustomEvent {};
globalThis.window = { dispatchEvent() {}, location: { pathname: "/settings", assign() {} } };

const { default: apiClient } = await import("../../shared/services/apiClient.js");
const { getWhatsAppConfig, testWhatsAppConnection } = await import("./whatsappService.js");

test("connection test posts to the dedicated endpoint", async () => {
  const calls = [];
  apiClient.defaults.adapter = async (config) => {
    calls.push({ method: config.method, url: config.url });
    return { status: 200, statusText: "OK", headers: {}, config, data: { success: true } };
  };
  await testWhatsAppConnection();
  assert.deepEqual(calls, [{ method: "post", url: "/whatsapp/config/test-connection/" }]);
});

test("normal config loading continues to use the config GET endpoint", async () => {
  const calls = [];
  apiClient.defaults.adapter = async (config) => {
    calls.push({ method: config.method, url: config.url });
    return { status: 200, statusText: "OK", headers: {}, config, data: { id: 1 } };
  };
  await getWhatsAppConfig();
  assert.deepEqual(calls, [{ method: "get", url: "/whatsapp/config/" }]);
});
