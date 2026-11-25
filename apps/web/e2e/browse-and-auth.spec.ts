import { expect, test, type Page } from "@playwright/test";
import { seedPassword, seeded, signIn } from "./support";

const LISTING = "Furnished 1BHK off 80 Feet Road"; // seeded, owned by owner_ravi

async function signOut(page: Page) {
  const narrow = (page.viewportSize()?.width ?? 1366) < 1024;
  if (narrow) {
    await page.getByRole("button", { name: "Open menu" }).click();
  } else {
    await page.getByRole("button", { name: "User menu" }).click();
  }
  await page.getByRole("button", { name: "Sign Out" }).click();
}

test("a visitor can browse listings and is asked to sign in to apply", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Flatmate home" })).toBeVisible();

  await page.goto(`/properties?q=${encodeURIComponent(LISTING)}`);
  const card = page.getByRole("link", { name: new RegExp(LISTING) }).first();
  await expect(card).toBeVisible();
  await card.click();

  await expect(page).toHaveURL(/\/properties\/[0-9a-f-]{36}/);
  await expect(page.getByRole("heading", { name: LISTING })).toBeVisible();
  await page.getByRole("button", { name: "Apply for this place" }).click();
  await expect(page).toHaveURL(/\/login\?next=%2Fproperties%2F/);
});

test("a member signs in, sees their space, and signs out", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email Address").fill(seeded("priya"));
  await page.getByLabel("Password").fill("definitely-not-the-password");
  await page.getByRole("button", { name: "Sign In" }).click();
  // Not any role=alert: Next.js's route announcer is one, so that would pass before the reply.
  await expect(page.getByRole("alert").filter({ hasText: /invalid email or password/i })).toBeVisible();
  await expect(page).toHaveURL(/\/login/);

  await signIn(page, seeded("priya"), seedPassword(), "/dashboard");
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole("heading", { name: "Priya Sharma" })).toBeVisible();

  await signOut(page);
  await page.goto("/notifications");
  await expect(page.getByText("Sign in to see your notifications.")).toBeVisible();
});

test("members who aren't admins can't open the admin console", async ({ page }) => {
  await signIn(page, seeded("arjun"), seedPassword(), "/admin");
  await expect(page.getByRole("heading", { name: "Access Denied" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Admin & Moderation Console" })).toHaveCount(0);
});
