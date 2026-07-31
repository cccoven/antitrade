import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  AUTH_TOKEN_STORAGE_KEY,
  completeAuthentication,
} from "../src/auth/complete-authentication.ts";

test("successful authentication stores the token before reloading the current page", () => {
  const events: string[] = [];

  completeAuthentication("fresh-token", {
    storage: {
      setItem(key, value) {
        events.push(`store:${key}:${value}`);
      },
    },
    reload() {
      events.push("reload");
    },
  });

  assert.deepEqual(events, [
    `store:${AUTH_TOKEN_STORAGE_KEY}:fresh-token`,
    "reload",
  ]);
});

test("all initial authentication paths finish with a page refresh", () => {
  const source = readFileSync(
    new URL("../src/auth/auth-context.tsx", import.meta.url),
    "utf8",
  );
  const completions = source.match(/finishAuthentication\(res\);/g) ?? [];

  assert.equal(completions.length, 4);
});
