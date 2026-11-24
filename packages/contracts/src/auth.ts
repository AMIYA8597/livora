export type UserRole = 'seeker' | 'tenant' | 'owner' | 'pg_operator' | 'broker' | 'moderator' | 'admin' | 'super_admin';

export interface UserDTO {
  id: string;
  email: string;
  full_name: string;
  phone_number?: string | null;
  /** True once the current phone_number was confirmed by SMS code. */
  phone_verified?: boolean;
  role: UserRole;
  roles?: string[];
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: UserDTO;
  tokens: AuthTokens;
  roles?: string[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserDTO;
  roles?: string[];
  /** True when this sign-in cancelled a pending account deletion. */
  account_restored?: boolean;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  role?: UserRole;
  additional_roles?: string[];
  phone_number?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface SendOtpRequest {
  phone_number: string;
}

export interface VerifyOtpRequest {
  phone_number: string;
  otp_code: string;
}

export interface SendOtpResponse {
  success: boolean;
  message: string;
  already_verified?: boolean;
  /** Seconds until the code expires. */
  expires_in?: number;
  /** Seconds before another code may be requested. */
  resend_after?: number;
  /** Only returned by development/test servers. */
  dev_code?: string;
}

export interface VerifyOtpResponse {
  success: boolean;
  message: string;
  phone_number: string;
}
