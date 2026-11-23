"use client";

import type {
  DealbreakerDTO,
  Lifestyle10DimensionDTO,
  PrivacySettingsDTO,
  ProfileDTO,
  UserTrustStatusDTO,
} from "@flatmate/contracts";
import { useApiQuery } from "@/hooks/useApiQuery";

/**
 * Everything the profile and dashboard pages show about the signed-in user.
 * Profile and lifestyle answer 404 until first saved; that is "empty", not an error.
 */
export function useMyProfileData(enabled: boolean) {
  const profile = useApiQuery<ProfileDTO | null>(enabled ? "/profiles/me" : null, undefined, { allowNotFound: true });
  const lifestyle = useApiQuery<Lifestyle10DimensionDTO | null>(enabled ? "/lifestyle/me" : null, undefined, { allowNotFound: true });
  const dealbreakers = useApiQuery<DealbreakerDTO[]>(enabled ? "/lifestyle/dealbreakers" : null);
  const privacy = useApiQuery<PrivacySettingsDTO | null>(enabled ? "/profiles/me/privacy" : null, undefined, { allowNotFound: true });
  const trust = useApiQuery<UserTrustStatusDTO>(enabled ? "/verification/status" : null);
  return { profile, lifestyle, dealbreakers, privacy, trust };
}
