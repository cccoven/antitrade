import assert from "node:assert/strict";
import test from "node:test";
import type { TFunction } from "i18next";
import {
  ASSISTANT_COMMANDS,
  parseAssistantCommandInput,
  resolveAssistantCommands,
  serializeAssistantCommandInput,
} from "../src/pages/assistant/command-registry";

const echoTranslation = ((key: string) => key) as TFunction;

test("assistant commands are unique and preserve the four featured market shortcuts", () => {
  const names = ASSISTANT_COMMANDS.map((item) => item.command);
  assert.equal(new Set(names).size, names.length);
  assert.deepEqual(
    ASSISTANT_COMMANDS.filter((item) => item.featured).map((item) => item.command),
    ["/stock", "/forex", "/crypto", "/macro"],
  );
});

test("slash command matching filters by command name", () => {
  assert.deepEqual(
    resolveAssistantCommands("port", echoTranslation).map((item) => item.command),
    ["/portfolio"],
  );
});

test("backend capabilities limit the visible command list", () => {
  assert.deepEqual(
    resolveAssistantCommands("", echoTranslation, ["/stock", "/help"])
      .map((item) => item.command),
    ["/stock", "/help"],
  );
});

test("recognized commands become ordered, unique tokens anywhere in the input", () => {
  assert.deepEqual(
    parseAssistantCommandInput("Compare /stock AAPL with /news and /stock again"),
    {
      commands: ["/stock", "/news"],
      text: "Compare AAPL with and again",
    },
  );
});

test("command tokens serialize back into a backend-compatible message", () => {
  assert.equal(
    serializeAssistantCommandInput(["/stock", "/news"], "Compare AAPL"),
    "/stock /news Compare AAPL",
  );
});
