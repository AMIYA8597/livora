import { test } from "node:test";
import assert from "node:assert/strict";
import type { ConversationDTO, MessageDTO } from "@flatmate/contracts";
import {
  applyIncomingToInbox,
  applyReadEvent,
  conversationTitle,
  deliveryStatus,
  mergeFetched,
  presenceLabel,
  safetyWarning,
  senderName,
  time,
  typingLabel,
  upsertMessage,
  withSafetyWarning,
} from "../features/messaging/chat-model.ts";

const ME = "me";
const person = (user_id: string, full_name: string) => ({
  id: `p-${user_id}`, conversation_id: "c1", user_id, role: "member" as const, joined_at: "", is_active: true,
  user: { id: user_id, full_name },
});

const conv = (over: Partial<ConversationDTO> = {}): ConversationDTO => ({
  id: "c1", type: "direct", status: "active", participants: [], created_at: "", last_message_at: "",
  participant_details: [person(ME, "Me Myself"), person("u2", "Bilal Khan")],
  ...over,
} as ConversationDTO);

const msg = (over: Partial<MessageDTO>): MessageDTO => ({
  id: "m", conversation_id: "c1", sender_id: "u2", content: "hi", message_type: "text",
  is_edited: false, is_deleted: false, is_read: false, sent_at: "2026-11-23T10:00:00.000Z", ...over,
});

test("chat: API timestamps with microseconds and +00:00 compare correctly with browser ones", () => {
  assert.equal(time("2026-11-23T10:00:00.123456+00:00"), time("2026-11-23T10:00:00.123Z"));
});

test("chat: a one-to-one chat is titled with the other person's name, never a placeholder", () => {
  assert.equal(conversationTitle(conv({ title: "Flatmate Seeker" }), ME), "Bilal Khan");
  assert.equal(conversationTitle(conv({ type: "group", title: null, participant_details: [
    person(ME, "Me"), person("a", "Asha"), person("b", "Bilal"), person("c", "Chen"), person("d", "Dev"),
  ] }), ME), "Asha, Bilal and 2 others");
  assert.equal(senderName(conv(), "u2", ME), "Bilal Khan");
  assert.equal(senderName(conv(), ME, ME), "You");
  assert.equal(senderName(conv(), "gone", ME), "Former member");
});

test("chat: the server's copy replaces the optimistic message (matched by idempotency key)", () => {
  const optimistic = msg({ id: "temp-1", sender_id: ME, idempotency_key: "k1", status: "sending" });
  const saved = msg({ id: "real-1", sender_id: ME, idempotency_key: "k1", status: "sent", sent_at: "2026-11-23T10:00:00.5+00:00" });
  const list = upsertMessage([msg({ id: "m0", sent_at: "2026-11-23T09:00:00Z" }), optimistic], saved);
  assert.deepEqual(list.map((m) => m.id), ["m0", "real-1"]);
  assert.equal(list[1].status, "sent");
  // A late arrival is placed in time order.
  const late = upsertMessage(list, msg({ id: "m-early", sent_at: "2026-11-23T09:30:00Z" }));
  assert.deepEqual(late.map((m) => m.id), ["m0", "m-early", "real-1"]);
});

test("chat: refetching after a reconnect keeps messages that are still unsent", () => {
  const failed = msg({ id: "temp-2", sender_id: ME, idempotency_key: "k2", status: "failed", sent_at: "2026-11-23T11:00:00Z" });
  const merged = mergeFetched([failed], [msg({ id: "m1" })]);
  assert.deepEqual(merged.map((m) => m.id), ["m1", "temp-2"]);
});

test("chat: a message confirmed while the refetch was in flight is not dropped", () => {
  // The re-sent message is saved (status "sent") before an older GET response lands.
  const confirmed = msg({ id: "real-3", sender_id: ME, idempotency_key: "k3", status: "sent", sent_at: "2026-11-23T11:05:00.1+00:00" });
  const staleOld = msg({ id: "gone", sent_at: "2026-11-23T08:00:00Z" }); // not in the page any more: dropped
  const merged = mergeFetched([staleOld, confirmed], [msg({ id: "m1", sent_at: "2026-11-23T10:00:00Z" })]);
  assert.deepEqual(merged.map((m) => m.id), ["m1", "real-3"]);
});

test("chat: read receipts come from the other people's read positions", () => {
  const mine = msg({ id: "x", sender_id: ME, sent_at: "2026-11-23T10:00:00Z" });
  assert.equal(deliveryStatus(mine, []), "sent");
  let cursors = applyReadEvent([], { user_id: "u2", read_at: "2026-11-23T10:00:05.000001+00:00" });
  assert.equal(deliveryStatus(mine, cursors), "read");
  assert.equal(deliveryStatus(msg({ sender_id: ME, sent_at: "2026-11-23T10:01:00Z" }), cursors), "sent");
  // Cursors never move backwards.
  cursors = applyReadEvent(cursors, { user_id: "u2", read_at: "2026-11-23T09:00:00Z" });
  assert.equal(cursors[0].last_read_at, "2026-11-23T10:00:05.000001+00:00");
  assert.equal(deliveryStatus({ ...mine, status: "failed" }, cursors), "failed");
});

test("chat: an incoming message moves its conversation to the top and counts as unread", () => {
  const list = [conv({ id: "a", unread_count: 0 }), conv({ id: "c1", unread_count: 1 })];
  const { list: next, known } = applyIncomingToInbox(list, msg({ id: "n" }), ME, "a");
  assert.equal(known, true);
  assert.deepEqual(next.map((c) => c.id), ["c1", "a"]);
  assert.equal(next[0].unread_count, 2);
  // My own message (sent from another tab) is never unread; the open conversation isn't either.
  assert.equal(applyIncomingToInbox(list, msg({ sender_id: ME }), ME, null).list[0].unread_count, 0);
  assert.equal(applyIncomingToInbox(list, msg({}), ME, "c1").list[0].unread_count, 0);
  assert.equal(applyIncomingToInbox(list, msg({ conversation_id: "new" }), ME, null).known, false);
});

test("chat: presence and typing labels", () => {
  const now = Date.parse("2026-11-23T12:00:00Z");
  assert.equal(presenceLabel({ status: "online" }, now), "Online");
  assert.equal(presenceLabel({ status: "offline", last_seen_at: "2026-11-23T11:55:00Z" }, now), "Last seen 5 min ago");
  assert.equal(presenceLabel({ status: "offline", last_seen_at: null }, now), null);
  assert.equal(typingLabel([]), null);
  assert.equal(typingLabel(["Bilal"]), "Bilal is typing…");
  assert.equal(typingLabel(["A", "B", "C"]), "Several people are typing…");
});

test("safety warnings from moderation are set, replaced and lifted without touching other metadata", () => {
  const m = msg({ id: "m1", metadata: { client: "web" } });
  assert.equal(safetyWarning(m), null);
  const warned = withSafetyWarning(m, "Never pay before a visit.");
  assert.equal(safetyWarning(warned), "Never pay before a visit.");
  assert.equal(warned.metadata?.client, "web");
  assert.equal(m.metadata?.safety_warning, undefined); // not mutated
  const lifted = withSafetyWarning(warned, null);
  assert.equal(safetyWarning(lifted), null);
  assert.equal(lifted.metadata?.client, "web");
  assert.equal(safetyWarning(msg({ metadata: { safety_warning: "  " } })), null);
  assert.equal(safetyWarning(msg({ metadata: { safety_warning: 42 } })), null);
});
