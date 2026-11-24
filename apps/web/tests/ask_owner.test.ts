import test from "node:test";
import assert from "node:assert/strict";
import { LISTING_QUICK_QUESTIONS } from "../../../packages/contracts/src/messaging.ts";
import { ASK_MAX_CHARS, composeOwnerQuestion } from "../lib/ask-owner.ts";

test("ask the owner: quick questions in list order, then the person's own words", () => {
  const text = composeOwnerQuestion(LISTING_QUICK_QUESTIONS, ["visitors", "deposit"], "  I work from home.  ");
  assert.deepEqual(text.split("\n"), [
    LISTING_QUICK_QUESTIONS.find((q) => q.key === "deposit")!.text,
    LISTING_QUICK_QUESTIONS.find((q) => q.key === "visitors")!.text,
    "I work from home.",
  ]);
  assert.equal(composeOwnerQuestion(LISTING_QUICK_QUESTIONS, [], "   "), "");
  assert.equal(composeOwnerQuestion(LISTING_QUICK_QUESTIONS, [], "Hi"), "Hi");
});

test("ask the owner: every quick question fits in one first message", () => {
  const all = composeOwnerQuestion(LISTING_QUICK_QUESTIONS, LISTING_QUICK_QUESTIONS.map((q) => q.key), "");
  assert.ok(all.length < ASK_MAX_CHARS);
  assert.equal(new Set(LISTING_QUICK_QUESTIONS.map((q) => q.key)).size, LISTING_QUICK_QUESTIONS.length);
});
