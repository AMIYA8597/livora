import { apiClient } from "@/lib/api-client";

export type ListingSignal = "view" | "save" | "unsave";

/**
 * Tell the API the signed-in person opened, saved or unsaved a listing, for their "Recommended"
 * order. Fire-and-forget: a failure never bothers the person. The API records nothing when they
 * turned personalised ranking off.
 */
export function sendListingSignal(propertyId: string, action: ListingSignal, position?: number): void {
  apiClient(`/properties/${propertyId}/interactions`, {
    method: "POST",
    body: JSON.stringify(position === undefined ? { action } : { action, position }),
  }).catch(() => undefined);
}
