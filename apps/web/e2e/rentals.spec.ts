import { expect, test } from "@playwright/test";
import { API, apiCall, apiLogin, registerSeeker, seeded, signIn, uniqueTag } from "./support";

const LISTING = "Furnished 1BHK off 80 Feet Road"; // seeded, owned by owner_ravi

test("a seeker applies, the owner accepts, and the seeker is told", async ({ browser, request }) => {
  const name = `Esha Test ${uniqueTag()}`;
  const seeker = await registerSeeker(request, name);
  const owner = await apiLogin(request, seeded("owner_ravi"));
  const listings = await apiCall<{ id: string; title: string; owner_id: string }[]>(
    request, owner.token, "GET", `/properties?limit=100&q=${encodeURIComponent(LISTING)}`,
  );
  const listing = listings.find((p) => p.title === LISTING && p.owner_id === owner.id);
  expect(listing, `seeded listing "${LISTING}"`).toBeTruthy();

  // Seeker applies through the listing page.
  const seekerCtx = await browser.newContext();
  const seekerPage = await seekerCtx.newPage();
  await signIn(seekerPage, seeker.email, seeker.password, `/properties/${listing!.id}`);
  await seekerPage.getByRole("button", { name: "Apply for this place" }).click();
  await seekerPage.getByLabel("Introduction to the landlord").fill(
    "Hi Ravi, I'm a product designer who works from the office most days. Quiet, tidy and non-smoking.",
  );
  const moveIn = new Date(Date.now() + 30 * 86_400_000).toISOString().slice(0, 10);
  await seekerPage.getByLabel("Move-in date").fill(moveIn);
  await seekerPage.getByRole("button", { name: "Send application" }).click();
  await expect(seekerPage.getByRole("heading", { name: "Application sent" })).toBeVisible();

  // Owner accepts it from the owner portal (the notification's link lands on this tab).
  const ownerCtx = await browser.newContext();
  const ownerPage = await ownerCtx.newPage();
  await signIn(ownerPage, owner.email, owner.password, "/owner?tab=applications");
  const card = ownerPage.locator("div", { has: ownerPage.getByRole("heading", { name }) }).filter({
    has: ownerPage.getByRole("button", { name: "Accept" }),
  }).last();
  await card.getByRole("button", { name: "Accept" }).click();
  await expect(ownerPage.getByText("Application accepted. The applicant has been notified.")).toBeVisible();

  // Seeker sees it in their space and in their notifications.
  await seekerPage.goto("/dashboard?tab=applications");
  await expect(seekerPage.getByText(/accepted/i).first()).toBeVisible();
  await seekerPage.goto("/notifications");
  await expect(seekerPage.getByText("Your application was accepted")).toBeVisible();

  await seekerCtx.close();
  await ownerCtx.close();
});

test("a chat message arrives live, with a notification that opens the chat", async ({ browser, request }) => {
  // Two new members, so each run (and each viewport) has its own conversation.
  const tag = uniqueTag();
  const sender = await registerSeeker(request, `Kabir ${tag}`);
  const reader = await registerSeeker(request, `Meera ${tag}`);
  const { conversation_id: conversationId } = await apiCall<{ conversation_id: string }>(
    request, sender.token, "POST", "/messaging/conversations",
    { participant_user_ids: [reader.id], type: "direct" },
  );

  const readerCtx = await browser.newContext();
  const readerPage = await readerCtx.newPage();
  await signIn(readerPage, reader.email, reader.password, "/notifications");
  await expect(readerPage.getByText("Nothing here yet")).toBeVisible();

  const senderCtx = await browser.newContext();
  const senderPage = await senderCtx.newPage();
  await signIn(senderPage, sender.email, sender.password, `/messages?conversationId=${conversationId}`);
  const text = `Is the room still free? ${tag}`;
  const box = senderPage.getByPlaceholder("Type a message…");
  await box.fill(text);
  await box.press("Enter");
  await expect(senderPage.getByText(text).filter({ visible: true }).first()).toBeVisible();

  // The reader's open page gets it over the socket: no reload.
  const live = readerPage.getByRole("button", { name: /New message from Kabir/ }).first();
  await expect(live).toBeVisible();
  await expect(readerPage.getByRole("button", { name: "Notifications, 1 unread" })).toBeVisible();
  // The notification never carries the message itself.
  await expect(readerPage.getByText(text)).toHaveCount(0);

  await live.click();
  await expect(readerPage).toHaveURL(new RegExp(`/messages\\?conversationId=${conversationId}`));
  await expect(readerPage.getByText(text).filter({ visible: true }).first()).toBeVisible();

  await readerCtx.close();
  await senderCtx.close();
});

test("the API the browser uses is reachable", async ({ request }) => {
  const res = await request.get(API.replace(/\/api\/v1$/, "/health"));
  expect(res.ok()).toBeTruthy();
});
