/**
 * Lifestyle answers and dealbreaker rules, using exactly the values the API scores
 * (apps/api/app/modules/lifestyle/service.py) and the matching engine enforces
 * (apps/api/app/modules/matching/engine.py). Values the engine does not know score as unknowns,
 * so add new options on the backend first.
 */
import type { Lifestyle10DimensionDTO } from "@flatmate/contracts";

export interface Option {
  value: string;
  label: string;
}

export const SLEEP_OPTIONS: Option[] = [
  { value: "early_bird", label: "Early bird (asleep by 11pm)" },
  { value: "night_owl", label: "Night owl (asleep after 1am)" },
  { value: "flexible", label: "Flexible / variable hours" },
  { value: "rotational", label: "Rotational shifts" },
];

export const WORK_OPTIONS: Option[] = [
  { value: "remote", label: "Work from home (fully remote)" },
  { value: "hybrid", label: "Hybrid (2-3 office days)" },
  { value: "on_site", label: "Work from office (full-time)" },
  { value: "shift_work", label: "Shift work" },
];

export const DIET_OPTIONS: Option[] = [
  { value: "pure_veg", label: "Pure vegetarian" },
  { value: "jain", label: "Jain" },
  { value: "eggetarian", label: "Eggetarian" },
  { value: "non_veg", label: "Non-vegetarian" },
  { value: "vegan", label: "Vegan" },
];

/** Diets whose kitchen defaults to no non-veg cooking. */
export const VEG_KITCHEN_DIETS: readonly string[] = ["pure_veg", "jain", "vegan"];

export const SMOKING_OPTIONS: Option[] = [
  { value: "never", label: "Non-smoker" },
  { value: "outside_only", label: "Smokes outside only" },
  { value: "permitted", label: "Smoking is fine" },
];

export const PET_OPTIONS: Option[] = [
  { value: "loves_pets", label: "Love pets" },
  { value: "cats_and_dogs_ok", label: "Cats and dogs are fine" },
  { value: "cats_ok", label: "Cats only" },
  { value: "dogs_ok", label: "Dogs only" },
  { value: "no_pets", label: "No pets" },
  { value: "allergic", label: "Allergic to pets" },
];

export const SOCIAL_OPTIONS: Option[] = [
  { value: "introverted", label: "Introverted" },
  { value: "balanced", label: "Balanced" },
  { value: "extroverted", label: "Extroverted" },
];

export const NOISE_OPTIONS: Option[] = [
  { value: "quiet_library", label: "Library quiet" },
  { value: "moderate", label: "Moderate" },
  { value: "lively", label: "Lively" },
];

export const GUEST_OPTIONS: Option[] = [
  { value: "rarely", label: "Rarely" },
  { value: "advance_notice", label: "With advance notice" },
  { value: "occasional_weekends", label: "Occasional weekends" },
  { value: "open_house", label: "Open house" },
];

/** Defaults match the API's own defaults for a new lifestyle profile. */
export const LIFESTYLE_DEFAULTS: Required<
  Pick<
    Lifestyle10DimensionDTO,
    | "sleep_schedule"
    | "cleanliness_level"
    | "work_arrangement"
    | "diet_preference"
    | "smoking"
    | "pet_preference"
    | "social_battery"
    | "noise_tolerance"
    | "guests_policy"
  >
> = {
  sleep_schedule: "flexible",
  cleanliness_level: 3,
  work_arrangement: "hybrid",
  diet_preference: "pure_veg",
  smoking: "never",
  pet_preference: "cats_and_dogs_ok",
  social_battery: "balanced",
  noise_tolerance: "moderate",
  guests_policy: "occasional_weekends",
};

/** Only rules the matching engine enforces. `expected_value` is required by the API. */
export const DEALBREAKER_RULES: { value: string; label: string; expected: string }[] = [
  { value: "no_smoking_inside", label: "No smoking inside the flat", expected: "never" },
  { value: "pure_veg_kitchen_only", label: "Pure vegetarian kitchen only", expected: "pure_veg" },
  { value: "no_pets_allowed", label: "No pets in the home", expected: "no_pets" },
];

/** The label for a stored answer; values from before the form existed fall back to readable text. */
export function optionLabel(options: Option[], value: string | null | undefined): string | null {
  if (!value) return null;
  return options.find((o) => o.value === value)?.label ?? value.replace(/_/g, " ");
}

export function dealbreakerLabel(ruleKey: string): string {
  return DEALBREAKER_RULES.find((r) => r.value === ruleKey)?.label ?? ruleKey.replace(/_/g, " ");
}
