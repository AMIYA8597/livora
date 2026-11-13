export type UserRole = 'seeker' | 'owner' | 'admin';

export interface UserDTO {
  id: string;
  email: string;
  full_name: string;
  phone_number?: string | null;
  role: UserRole;
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
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserDTO;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  role?: UserRole;
  phone_number?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}
