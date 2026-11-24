import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

/** The API the web app talks to (same value the app was built with). */
export const API = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

/** Seeded accounts: `<key>@seed.example.com`. */
export const seeded = (key: string) => `${key}@seed.example.com`;

let cachedPassword: string | null = null;

/** The seed accounts' password: E2E_SEED_PASSWORD, or read from the seed script so it isn't copied here. */
export function seedPassword(): string {
  if (process.env.E2E_SEED_PASSWORD) return process.env.E2E_SEED_PASSWORD;
  if (cachedPassword) return cachedPassword;
  const seed = readFileSync(path.resolve(__dirname, "../../../database/seeds/seed.py"), "utf8");
  const match = seed.match(/SEED_PASSWORD\s*=\s*["']([^"']+)["']/);
  if (!match) throw new Error("SEED_PASSWORD not found in database/seeds/seed.py; set E2E_SEED_PASSWORD");
  cachedPassword = match[1];
  return cachedPassword;
}

/** A short unique tag so parallel runs (and both viewports) never collide. */
export const uniqueTag = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

export interface Session {
  id: string;
  email: string;
  password: string;
  token: string;
}

async function tokenOf(res: Awaited<ReturnType<APIRequestContext["post"]>>): Promise<string> {
  expect(res.ok(), `${res.url()} → ${res.status()} ${await res.text()}`).toBeTruthy();
  const body = (await res.json()) as { access_token?: string; tokens?: { access_token: string } };
  return (body.access_token ?? body.tokens?.access_token) as string;
}

export async function apiCall<T = unknown>(
  request: APIRequestContext,
  token: string,
  method: "GET" | "POST" | "PATCH",
  route: string,
  data?: unknown,
): Promise<T> {
  const res = await request.fetch(`${API}${route}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
    data,
  });
  expect(res.ok(), `${method} ${route} → ${res.status()} ${await res.text()}`).toBeTruthy();
  return (await res.json()) as T;
}

export async function apiLogin(request: APIRequestContext, email: string, password = seedPassword()): Promise<Session> {
  const token = await tokenOf(await request.post(`${API}/auth/login`, { data: { email, password } }));
  const me = await apiCall<{ id: string }>(request, token, "GET", "/auth/me");
  return { id: me.id, email, password, token };
}

/** A brand-new seeker, so journeys that change state start clean every run. */
export async function registerSeeker(request: APIRequestContext, fullName: string): Promise<Session> {
  const email = `e2e-${uniqueTag()}@example.com`;
  const password = `E2e-${uniqueTag()}-pass`;
  const token = await tokenOf(
    await request.post(`${API}/auth/register`, { data: { email, password, full_name: fullName, role: "seeker" } }),
  );
  const me = await apiCall<{ id: string }>(request, token, "GET", "/auth/me");
  return { id: me.id, email, password, token };
}

/** Sign in through the real form, landing on `next`. */
export async function signIn(page: Page, email: string, password: string, next = "/dashboard") {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email Address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}
