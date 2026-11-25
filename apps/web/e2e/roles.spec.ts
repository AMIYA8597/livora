import { expect, test, type Page } from "@playwright/test";
import { apiCall, apiLogin, registerSeeker, seeded, seedPassword, signIn, uniqueTag } from "./support";

/** Staff work in their own browser, next to the member's. */
async function staffPage(page: Page): Promise<Page> {
  const context = await page.context().browser()!.newContext({
    viewport: page.viewportSize(),
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
  });
  return context.newPage();
}

test("a member asks to be a broker, an admin approves, and they can list", async ({ page, request }) => {
  const tag = uniqueTag();
  const member = await registerSeeker(request, `Broker ${tag}`);

  // Listing is closed to a plain member.
  await signIn(page, member.email, member.password, "/owner");
  await expect(page.getByText(/This area is for property owners, PG operators and verified brokers/)).toBeVisible();

  // Ask from the profile.
  await page.goto("/profile");
  await page.getByRole("tab", { name: "Trust & verification" }).click();
  await page.getByLabel("About your work").fill(`Agency ${tag}, RERA PRM/KA/RERA/1251/309/AG/${tag}, Bengaluru`);
  await page.getByRole("button", { name: "Request broker access" }).click();
  await expect(page.getByTestId("broker-request-status").getByText("Waiting for review")).toBeVisible();

  // An admin approves it from the console.
  const admin = await staffPage(page);
  await signIn(admin, seeded("admin"), seedPassword(), "/admin");
  await admin.getByRole("button", { name: "Role Requests" }).click();
  const request_ = admin.getByTestId("role-request").filter({ hasText: member.email });
  await expect(request_).toBeVisible();
  await expect(request_.getByText(`Agency ${tag}`)).toBeVisible();
  await request_.getByRole("button", { name: "Approve" }).click();
  await admin.getByRole("dialog").getByRole("button", { name: "Approve" }).click();
  await expect(admin.getByText(`Broker ${tag} is now a broker.`)).toBeVisible();
  await expect(request_).toHaveCount(0);
  await admin.context().close();

  // The member is a broker now: the card says so and the listings area opens.
  await page.goto("/profile");
  await page.getByRole("tab", { name: "Trust & verification" }).click();
  await expect(page.getByText("You’re a verified broker.")).toBeVisible();
  await page.goto("/owner");
  await expect(page.getByText("Your listings, rooms, applications and viewing requests.")).toBeVisible();
});

test("a moderator sees only the moderation tools", async ({ page, request }) => {
  const tag = uniqueTag();
  const mod = await registerSeeker(request, `Moderator ${tag}`);
  const admin = await apiLogin(request, seeded("admin"));
  await apiCall(request, admin.token, "POST", `/admin/users/${mod.id}/roles`, { role: "moderator" });

  await signIn(page, mod.email, mod.password, "/admin");
  await expect(page.getByRole("heading", { name: "Admin & Moderation Console" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Moderation Queue/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Applications/ })).toBeVisible();
  for (const adminOnly of [/System Overview/, /User Management/, /Role Requests/, /Payment Events/]) {
    await expect(page.getByRole("button", { name: adminOnly })).toHaveCount(0);
  }
});
