import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/index.css", import.meta.url), "utf8");

test("theme font tokens keep the updated ui and caption scale", () => {
  assert.match(css, /--font-ui:\s*13px;/);
  assert.match(css, /--font-caption:\s*12px;/);
  assert.match(css, /--font-body:\s*13px;/);
  assert.match(css, /--font-heading:\s*18px;/);
});
