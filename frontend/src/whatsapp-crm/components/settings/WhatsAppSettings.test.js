import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("./WhatsAppSettings.jsx", import.meta.url), "utf8");

test("Test API Connection exposes loading, success metadata, and safe failure states", () => {
  assert.match(source, /await testWhatsAppConnection\(\)/);
  assert.match(source, /setIsTesting\(true\)/);
  assert.match(source, /disabled=\{isLoading \|\| isTesting\}/);
  assert.match(source, /isTesting \? "Testing\.\.\." : "Test API Connection"/);
  assert.match(source, /result\.data\?\.verified_name/);
  assert.match(source, /requestError\.response\?\.data\?\.message/);
});

test("saved active configuration is not labelled as a live connection", () => {
  assert.match(source, /"Configuration Active"/);
  assert.doesNotMatch(source, /savedConfig\?\.is_active \? "Connected"/);
});
