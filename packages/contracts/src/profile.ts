export type Gender = 'male' | 'female' | 'non_binary' | 'other' | 'prefer_not_to_say';
export type SleepSchedule = 'early_bird' | 'night_owl' | 'flexible';
export type CleanlinessLevel = 1 | 2 | 3 | 4 | 5;
export type SocialBattery = 'introverted' | 'moderate' | 'extroverted' | 'balanced';
export type WorkArrangement = 'remote' | 'hybrid' | 'on_site';
export type DietType = 'omnivore' | 'vegetarian' | 'vegan' | 'pescatarian' | 'halal' | 'kosher';
export type SmokingPolicy = 'never' | 'outside_only' | 'allowed';
export type PetPreference = 'loves_pets' | 'has_cat' | 'has_dog' | 'cats_ok' | 'dogs_ok' | 'no_pets';

export interface LifestyleTraits {
  sleep_schedule: SleepSchedule;
  cleanliness_level: CleanlinessLevel;
  social_battery: SocialBattery;
  work_arrangement: WorkArrangement;
  diet: DietType;
  smoking: SmokingPolicy;
  pets: PetPreference;
  guests_policy: string;
}

export interface ProfileDTO {
  id: string;
  user_id: string;
  display_name: string;
  avatar_url?: string | null;
  bio?: string | null;
  birth_date?: string | null;
  gender?: Gender | null;
  occupation?: string | null;
  budget_min: number;
  budget_max: number;
  move_in_date?: string | null;
  lease_duration_months?: number;
  lifestyle_traits: LifestyleTraits;
  preferred_locations: string[];
  created_at: string;
  updated_at: string;
}

export interface ProfileUpdateInput {
  display_name?: string;
  avatar_url?: string;
  bio?: string;
  birth_date?: string;
  gender?: Gender;
  occupation?: string;
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
  diet: DietType;
  smoking: SmokingPolicy;
  pets: PetPreference;
  guests_policy: string;
}
