export type Gender = 'male' | 'female' | 'non_binary' | 'other' | 'prefer_not_to_say';
export type SleepSchedule = 'early_bird' | 'night_owl' | 'flexible' | 'rotational';
export type CleanlinessLevel = 1 | 2 | 3 | 4 | 5;
export type SocialBattery = 'introverted' | 'moderate' | 'extroverted' | 'balanced';
export type WorkArrangement = 'remote' | 'hybrid' | 'on_site' | 'shift_work';
export type DietType = 'omnivore' | 'vegetarian' | 'vegan' | 'pescatarian' | 'halal' | 'kosher' | 'pure_veg' | 'eggetarian' | 'non_veg' | 'jain';
export type SmokingPolicy = 'never' | 'outside_only' | 'allowed' | 'permitted';
export type PetPreference = 'loves_pets' | 'has_cat' | 'has_dog' | 'cats_ok' | 'dogs_ok' | 'no_pets' | 'cats_and_dogs_ok' | 'allergic';

export interface LifestyleTraits {
  sleep_schedule: SleepSchedule;
  cleanliness_level: CleanlinessLevel;
  social_battery: SocialBattery;
  work_arrangement: WorkArrangement;
  diet?: DietType;
  diet_preference?: DietType | string;
  smoking: SmokingPolicy;
  pets?: PetPreference;
  pet_preference?: PetPreference | string;
  guests_policy: string;
  [key: string]: any;
}

export interface ProfileDTO {
  id: string;
  user_id: string;
  /** Has a verified work or college email. */
  is_verified?: boolean;
  display_name: string;
  avatar_url?: string | null;
  bio?: string | null;
  birth_date?: string | null;
  gender?: Gender | string | null;
  occupation?: string | null;
  education_institute?: string | null;
  education_degree?: string | null;
  company_name?: string | null;
  designation?: string | null;
  budget_min: number;
  budget_max: number;
  move_in_date?: string | null;
  lease_duration_months?: number;
  lifestyle_traits: LifestyleTraits;
  preferred_locations: string[];
  phone_number?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProfileUpdateInput {
  display_name?: string;
  avatar_url?: string;
  bio?: string;
  birth_date?: string;
  gender?: Gender | string;
  occupation?: string;
  education_institute?: string;
  education_degree?: string;
  company_name?: string;
  designation?: string;
  budget_min?: number;
  budget_max?: number;
  move_in_date?: string;
  lease_duration_months?: number;
  preferred_locations?: string[];
}

export interface LifestyleQuizInput {
  sleep_schedule: SleepSchedule;
  cleanliness_level: CleanlinessLevel;
  social_battery: SocialBattery;
  work_arrangement: WorkArrangement;
  diet?: DietType;
  smoking: SmokingPolicy;
  pets?: PetPreference;
  guests_policy: string;
}

export interface Lifestyle10DimensionDTO {
  id?: string;
  user_id?: string;
  sleep_schedule: string;
  wake_time_typical?: string;
  sleep_time_typical?: string;
  work_arrangement: string;
  cleanliness_level: number;
  chore_philosophy?: string;
  noise_tolerance?: string;
  instrument_or_music?: boolean;
  lighting_preference?: string;
  guests_policy: string;
  social_battery: string;
  diet_preference: string;
  non_veg_cooking_allowed?: boolean;
  cooks_at_home?: string;
  smoking: string;
  drinking?: string;
  pet_preference: string;
  custom_notes?: string | null;
}

export interface DealbreakerDTO {
  id: string;
  user_id: string;
  rule_key: string;
  is_strict: boolean;
  expected_value: string;
  created_at: string;
}

export interface DealbreakerCreateInput {
  rule_key: string;
  is_strict?: boolean;
  expected_value: string;
}

export interface PrivacySettingsDTO {
  id: string;
  user_id: string;
  show_phone_publicly: boolean;
  show_exact_location: boolean;
  allow_direct_messages: boolean;
  profile_visibility: 'public' | 'matched_only' | 'private' | string;
  updated_at: string;
}

export interface PrivacySettingsUpdateInput {
  show_phone_publicly?: boolean;
  show_exact_location?: boolean;
  allow_direct_messages?: boolean;
  profile_visibility?: 'public' | 'matched_only' | 'private' | string;
}
