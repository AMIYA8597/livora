/**
 * Web Push on this device: register the service worker, subscribe with the server's VAPID key,
 * and keep the server's copy of the subscription in step with the signed-in account.
 *
 * iPhone and iPad only allow push for sites added to the Home Screen (iOS 16.4+).
 */
import type { PushConfigDTO } from "@flatmate/contracts";
import { apiClient } from "./api-client.ts";
import { urlBase64ToUint8Array } from "./notifications-model.ts";

export type PushState =
  | "unsupported" // no service worker / Push API (or iOS outside the Home Screen app)
  | "unavailable" // the server has no VAPID keys
  | "denied" // the user blocked notifications for this site
  | "off"
  | "on";

const SW_URL = "/sw.js";

export function pushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

/** True on iPhone/iPad Safari outside an installed Home Screen app, where push can't work. */
export function needsHomeScreen(): boolean {
  if (typeof window === "undefined") return false;
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent);
  const standalone = window.matchMedia?.("(display-mode: standalone)").matches;
  return ios && !standalone;
}

async function registration(): Promise<ServiceWorkerRegistration> {
  const existing = await navigator.serviceWorker.getRegistration(SW_URL);
  return existing ?? navigator.serviceWorker.register(SW_URL, { scope: "/" });
}

async function currentSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration(SW_URL);
  return reg ? reg.pushManager.getSubscription() : null;
}

function toBody(sub: PushSubscription) {
  const json = sub.toJSON();
  return { endpoint: sub.endpoint, keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" } };
}

export async function getPushState(config?: PushConfigDTO | null): Promise<PushState> {
  if (!pushSupported() || needsHomeScreen()) return "unsupported";
  if (config && !config.enabled) return "unavailable";
  if (Notification.permission === "denied") return "denied";
  const sub = await currentSubscription();
  return sub && Notification.permission === "granted" ? "on" : "off";
}

/** Ask permission (must run from a click), subscribe this browser and register it. */
export async function enablePush(): Promise<PushState> {
  if (!pushSupported() || needsHomeScreen()) return "unsupported";
  const config = await apiClient<PushConfigDTO>("/notifications/push/config");
  if (!config.enabled || !config.public_key) return "unavailable";
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission === "denied" ? "denied" : "off";

  const reg = await registration();
  await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  const key = urlBase64ToUint8Array(config.public_key);
  if (sub) {
    // A subscription made with an older server key can't receive our pushes: replace it.
    const current = sub.options.applicationServerKey;
    const same = current && new Uint8Array(current).every((b, i) => b === key[i]);
    if (!same) {
      await sub.unsubscribe();
      sub = null;
    }
  }
  sub ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key as BufferSource });
  await apiClient("/notifications/push/subscriptions", { method: "POST", body: JSON.stringify(toBody(sub)) });
  return "on";
}

/** Stop pushes to this browser (server first, so nothing is sent while we unsubscribe). */
export async function disablePush(): Promise<PushState> {
  const sub = await currentSubscription();
  if (sub) {
    await apiClient("/notifications/push/unsubscribe", {
      method: "POST",
      body: JSON.stringify({ endpoint: sub.endpoint }),
    }).catch(() => undefined);
    await sub.unsubscribe().catch(() => undefined);
  }
  return "off";
}

/**
 * On app start: if this browser is subscribed, re-register it for whoever is signed in now
 * (subscriptions can change, and a shared computer may have switched accounts).
 */
export async function syncPushSubscription(): Promise<void> {
  if (!pushSupported() || Notification.permission !== "granted") return;
  const sub = await currentSubscription();
  if (sub) {
    await apiClient("/notifications/push/subscriptions", { method: "POST", body: JSON.stringify(toBody(sub)) });
  }
}

/** On sign-out: the next person on this browser must not get the previous account's pushes. */
export async function forgetPushSubscription(): Promise<void> {
  if (!pushSupported()) return;
  await disablePush();
}
