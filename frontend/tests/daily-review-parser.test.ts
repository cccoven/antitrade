import test from "node:test";
import assert from "node:assert/strict";

import {
  parseReviewBody,
  serializeReviewBlocks,
  type ReviewBlock,
} from "../src/pages/daily-review/parser";

test("empty string parses to a single empty text block", () => {
  assert.deepEqual(parseReviewBody(""), [{ kind: "text", text: "" }]);
});

test("plain markdown with no embeds is a single text block", () => {
  const body = "# title\n\nbody text\nline 2";
  assert.deepEqual(parseReviewBody(body), [{ kind: "text", text: body }]);
});

test("trade and screenshot embeds split text", () => {
  const body = 'before\n::trade id="t1"::\nmiddle\n::screenshot id="s1"::\nafter';
  const blocks = parseReviewBody(body);
  assert.deepEqual(blocks, [
    { kind: "text", text: "before" },
    { kind: "trade", id: "t1" },
    { kind: "text", text: "middle" },
    { kind: "screenshot", id: "s1" },
    { kind: "text", text: "after" },
  ]);
});

test("consecutive embeds are separated by an empty text block", () => {
  const body = '::trade id="t1"::\n::trade id="t2"::';
  assert.deepEqual(parseReviewBody(body), [
    { kind: "text", text: "" },
    { kind: "trade", id: "t1" },
    { kind: "text", text: "" },
    { kind: "trade", id: "t2" },
    { kind: "text", text: "" },
  ]);
});

test("malformed embed line is treated as text", () => {
  const body = '::trade::\nok';
  assert.deepEqual(parseReviewBody(body), [
    { kind: "text", text: "::trade::\nok" },
  ]);
});

test("serialize round-trips parse for representative bodies", () => {
  const cases = [
    "",
    "abc\ndef",
    'before\n::trade id="t1"::\nafter',
    '::trade id="t1"::\n::screenshot id="s1"::',
  ];
  for (const body of cases) {
    const blocks = parseReviewBody(body);
    assert.equal(serializeReviewBlocks(blocks), body);
  }
});
