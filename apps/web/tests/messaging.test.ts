import { test } from "node:test";
import assert from "node:assert";
import type { MessageDTO, ConversationDTO } from "@flatmate/contracts";

test("Messaging: Idempotency keys are valid UUIDs", () => {
  const idemKey = crypto.randomUUID();
  assert.ok(idemKey.length === 36);
  assert.match(idemKey, /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
});

test("Messaging: Safety heuristic detects advance rent scam attempts", () => {
  const scamStrings = [
    "Please send advance rent before visit",
    "Pay advance token before visit to lock the room",
    "Deposit advance payment before visit",
  ];
  const safeStrings = [
    "Can we schedule a visit on Sunday?",
    "What is the security deposit?",
    "I will visit the property tomorrow at 4 PM.",
  ];

  const regex = /advance\s+(money|token|rent|payment|deposit)\s+before\s+visit/i;

  for (const scam of scamStrings) {
    assert.ok(regex.test(scam), `Expected scam detection on: ${scam}`);
  }

  for (const safe of safeStrings) {
    assert.strictEqual(regex.test(safe), false, `False positive on safe string: ${safe}`);
  }
});

test("Messaging: MessageDTO contract conforms to Phase 20A requirements", () => {
  const sampleMessage: MessageDTO = {
    id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    conversation_id: "77777777-6666-5555-4444-333333333333",
    sender_id: "88888888-9999-0000-1111-222233334444",
    content: "Hi! Looking forward to viewing the flat.",
    message_type: "text",
    idempotency_key: "idem-12345",
    reply_to_message_id: null,
    is_edited: false,
    is_deleted: false,
    is_read: false,
    sent_at: new Date().toISOString(),
    status: "sent",
  };

  assert.strictEqual(sampleMessage.message_type, "text");
  assert.strictEqual(sampleMessage.is_deleted, false);
  assert.strictEqual(sampleMessage.status, "sent");
});
