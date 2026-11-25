/** Which optional features the API has turned on (GET /meta/app-config `features`). Pure, so the
 *  rules are unit-tested; the fetch and the hook live in ./app-features. */

export interface AppFeatures {
  /** SMS codes. Off when the deployment has no SMS provider (SMS_PROVIDER=disabled). */
  phone_verification: boolean;
  /** Paid plans. Off when the deployment has no payment keys. */
  payments: boolean;
}

/** When the API can't be asked, show the features: a clear error from a working endpoint is
 *  better than hiding something that works. */
export const FEATURES_IF_UNKNOWN: AppFeatures = { phone_verification: true, payments: true };

/** The features from an app-config answer. An older API without `features` means everything is on;
 *  anything but an explicit `false` counts as on. */
export function featuresFrom(config: unknown): AppFeatures {
  const raw = (config && typeof config === "object" ? (config as { features?: unknown }).features : null) ?? {};
  const flags = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return {
    phone_verification: flags.phone_verification !== false,
    payments: flags.payments !== false,
  };
}
