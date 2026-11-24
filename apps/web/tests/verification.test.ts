import { test } from "node:test";
import assert from "node:assert/strict";
import { badgeLabel, emailHint, trustSummary } from "../lib/verification-model.ts";

test("badges read as what was actually checked", () => {
  assert.equal(badgeLabel("phone"), "Mobile");
  assert.equal(badgeLabel("work_email"), "Work email");
  assert.equal(badgeLabel("student_email"), "College email");
  assert.equal(badgeLabel("something_new"), "something new");
});

test("trust summary names the verified domains", () => {
  assert.equal(trustSummary([]), "Nothing verified yet");
  assert.equal(trustSummary(undefined), "Nothing verified yet");
  assert.equal(
    trustSummary(["phone", "work_email"], [{ verification_type: "work_email", email_domain: "acme.com" }]),
    "Mobile • Work email (acme.com)",
  );
});

test("email hints catch the common mistakes before sending", () => {
  assert.equal(emailHint("asha@infosys.com", "work_email"), null);
  assert.equal(emailHint("asha@iitb.ac.in", "student_email"), null);
  assert.equal(emailHint("asha@stanford.edu", "student_email"), null);
  assert.match(emailHint("asha@gmail.com", "work_email") ?? "", /Personal mailboxes/);
  assert.match(emailHint("asha@infosys.com", "student_email") ?? "", /academic domain/);
  assert.equal(emailHint("not an email", "work_email"), "Enter a valid email address");
});
