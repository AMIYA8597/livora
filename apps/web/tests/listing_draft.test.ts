import { test } from "node:test";
import assert from "node:assert/strict";
import { buildListingPayload, firstInvalidStep, initialDraft, newBed, validateStep, type ListingDraft } from "../features/listings/draft.ts";

function completeDraft(): ListingDraft {
  const d = initialDraft();
  d.city = "Pune";
  d.state = "Maharashtra";
  d.locality = "Baner";
  d.postalCode = "411045";
  d.monthlyRent = "30000";
  d.deposit = "90000";
  d.rooms[0].name = "Master";
  d.rooms[0].rent = "18000";
  return d;
}

test("listing draft: starts empty, so sample values can't be published by accident", () => {
  const invalid = firstInvalidStep(initialDraft());
  assert.equal(invalid?.step, 1);
  assert.match(invalid!.message, /city/i);
});

test("listing draft: location needs a supported city, locality and 6-digit PIN", () => {
  const d = completeDraft();
  assert.equal(validateStep(1, d), null);
  assert.match(validateStep(1, { ...d, city: "Atlantis" })!, /city/i);
  assert.match(validateStep(1, { ...d, postalCode: "4110" })!, /PIN/);
  assert.match(validateStep(1, { ...d, locality: " " })!, /locality/i);
});

test("listing draft: rooms need a name and rent; pricing needs rent and deposit", () => {
  const d = completeDraft();
  assert.match(validateStep(3, { ...d, rooms: [{ ...d.rooms[0], rent: "" }] })!, /rent/i);
  assert.match(validateStep(5, { ...d, monthlyRent: "0" })!, /rent/i);
  assert.equal(firstInvalidStep(d), null);
});

test("listing draft: payload sends rooms and beds, city-centre coordinates and no stock photo", () => {
  const d = completeDraft();
  d.rooms[0].type = "shared";
  d.rooms[0].beds = [newBed("Bed A"), { ...newBed("Bed B"), occupied: true }];
  const p = buildListingPayload(d, "2026-11-23");

  assert.deepEqual(p.images, []);
  assert.equal(p.latitude, 18.5204);
  assert.equal(p.address_display, "Baner, Pune");
  assert.equal(p.current_occupants, 1);
  assert.equal(p.rooms.length, 1);
  assert.equal(p.rooms[0].room_type, "2_sharing");
  assert.equal(p.rooms[0].occupied_beds, 1);
  // Blank bed rents split the room rent evenly.
  assert.deepEqual(p.rooms[0].beds.map((b) => b.monthly_rent), [9000, 9000]);
  assert.deepEqual(p.rooms[0].beds.map((b) => b.is_occupied), [false, true]);
  assert.equal(p.title, "2BHK in Baner, Pune");
});
