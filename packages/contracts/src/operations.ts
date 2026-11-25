export interface OwnerDashboardStatsDTO {
  total_properties: number;
  active_listings: number;
  total_applicants?: number;
  pending_applications?: number;
  total_active_tenants?: number;
  total_inquiries?: number;
  estimated_monthly_revenue?: number;
  available_rooms?: number;
  available_beds?: number;
  total_applications?: number;
  monthly_rental_value?: number;
}

export interface ApplicantReviewCardDTO {
  application_id: string;
  id?: string;
  applicant_id: string;
  applicant_name: string;
  applicant_email: string;
  applicant_phone?: string | null;
  property_id: string;
  property_title: string;
  room_id?: string | null;
  proposed_rent: number;
  move_in_target: string;
  status: string;
  trust_score: number;
  is_verified: boolean;
  submitted_at: string;
  introduction?: string | null;
}

export interface TenantRosterItemDTO {
  membership_id: string;
  tenant_id: string;
  tenant_name: string;
  tenant_email: string;
  tenant_phone?: string | null;
  room_name?: string | null;
  bed_identifier?: string | null;
  lease_start: string;
  lease_end?: string | null;
  monthly_rent: number;
  is_primary_tenant: boolean;
}

export interface TenantMembershipDTO {
  id: string;
  property_id: string;
  room_id?: string | null;
  bed_id?: string | null;
  tenant_id: string;
  lease_start: string;
  lease_end?: string | null;
  monthly_rent: number;
  status: string;
  is_primary_tenant: boolean;
  created_at: string;
}

export interface ExistingTenantVacancyCreateInput {
  property_id: string;
  room_id: string;
  title: string;
  description: string;
  vacant_from: string;
  expected_rent: number;
  deposit_required?: number;
  preferred_gender?: 'any' | 'female_only' | 'male_only' | string;
}

export interface ExistingTenantVacancyDTO {
  id: string;
  property_id: string;
  room_id: string;
  posted_by_tenant_id: string;
  title: string;
  description: string;
  vacant_from: string;
  expected_rent: number;
  deposit_required: number;
  preferred_gender: string;
  is_active: boolean;
  created_at: string;
}

export interface PGFloorDTO {
  id: string;
  pg_building_id: string;
  floor_number: number;
  gender_restriction: string;
  total_rooms: number;
}

export interface PGBuildingDTO {
  id: string;
  operator_id: string;
  property_id: string;
  building_name: string;
  pg_type: 'gents' | 'ladies' | 'coed' | string;
  total_floors: number;
  food_included: boolean;
  meal_type: string;
  meals_served_per_day: number;
  gate_closing_time?: string | null;
  notice_period_days: number;
  biometric_entry: boolean;
  created_at: string;
  floors?: PGFloorDTO[];
}

export interface PGBuildingCreateInput {
  property_id: string;
  building_name: string;
  pg_type?: string;
  total_floors?: number;
  food_included?: boolean;
  meal_type?: string;
  meals_served_per_day?: number;
  gate_closing_time?: string;
  notice_period_days?: number;
  biometric_entry?: boolean;
  floors?: Array<{
    floor_number: number;
    gender_restriction?: string;
    total_rooms?: number;
  }>;
}

export type NotificationCategory = 'messages' | 'matches' | 'rentals' | 'account';

export interface NotificationDTO {
  id: string;
  user_id: string;
  title: string;
  body: string;
  notification_type: string;
  category?: NotificationCategory | string;
  /** Same-site path to open; built by the server. */
  link?: string | null;
  reference_id?: string | null;
  is_read: boolean;
  created_at: string;
}

/** Which categories may send a push to this account's browsers. */
export type PushPreferencesDTO = Record<NotificationCategory, boolean>;

export interface PushConfigDTO {
  /** Web Push (browsers): on or off, and the VAPID key to subscribe with. */
  enabled: boolean;
  public_key?: string | null;
  /** App platforms whose native push (FCM / APNs) is on. */
  native_platforms?: AppPlatform[];
}

export type AppPlatform = "android" | "ios";

/** POST /notifications/push/devices: the app's push token, sent on every start. */
export interface DeviceRegisterRequest {
  platform: AppPlatform;
  token: string;
  app_version?: string | null;
}

export interface DeviceRegistrationResponse {
  registered: boolean;
  devices: number;
}

/** GET /meta/app-config: which app versions the API serves. Below `min_version` every call
 *  answers 426 with error_code CLIENT_UPGRADE_REQUIRED. Apps send X-Client-Platform and
 *  X-Client-Version on every request. */
export interface PlatformVersionsDTO {
  min_version?: string | null;
  latest_version?: string | null;
  update_url?: string | null;
}

/** Optional features that depend on paid providers; off means the app hides them. */
export interface AppFeaturesDTO {
  phone_verification: boolean;
  payments: boolean;
}

export interface AppConfigDTO {
  api_version: string;
  android: PlatformVersionsDTO;
  ios: PlatformVersionsDTO;
  features: AppFeaturesDTO;
}
