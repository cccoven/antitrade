import test from "node:test";
import assert from "node:assert/strict";

import type { ReviewBlock } from "../src/pages/daily-review/parser";
import {
  insertEmbedAt,
  removeEmbedAt,
  insertTextAt,
} from "../src/pages/daily-review/blocks";

test("insertEmbedAt at end of text block splits and inserts", () => {
  const blocks: ReviewBlock[] = [{ kind: "text", text: "hello" }];
  const next = insertEmbedAt(blocks, { textBlockIndex: 0, cursor: 5 }, {
    kind: "trade",
    id: "t1",
  });
  assert.deepEqual(next, [
    { kind: "text", text: "hello" },
    { kind: "trade", id: "t1" },
    { kind: "text", text: "" },
  ]);
});

test("insertEmbedAt mid-text splits text into two blocks", () => {
  const blocks: ReviewBlock[] = [{ kind: "text", text: "abcdef" }];
  const next = insertEmbedAt(blocks, { textBlockIndex: 0, cursor: 3 }, {
    kind: "trade",
    id: "t1",
  });
  assert.deepEqual(next, [
    { kind: "text", text: "abc" },
    { kind: "trade", id: "t1" },
    { kind: "text", text: "def" },
  ]);
});

test("removeEmbedAt merges adjacent text blocks", () => {
  const blocks: ReviewBlock[] = [
    { kind: "text", text: "before" },
    { kind: "trade", id: "t1" },
    { kind: "text", text: "after" },
  ];
  const next = removeEmbedAt(blocks, 1);
  assert.deepEqual(next, [{ kind: "text", text: "before\nafter" }]);
});

test("insertTextAt appends to a text block at cursor position", () => {
  const blocks: ReviewBlock[] = [{ kind: "text", text: "hello" }];
  const next = insertTextAt(blocks, { textBlockIndex: 0, cursor: 5 }, " world");
  assert.deepEqual(next, [{ kind: "text", text: "hello world" }]);
});
