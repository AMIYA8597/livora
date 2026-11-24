/**
 * Trust and verification. Work and college emails are verified by an emailed one-time code;
 * only the domain is kept. ID-document checks are switched off until a KYC provider is chosen.
 */
export type EmailVerificationType = 'work_email' | 'student_email';
/** Badges: 'phone' plus each verified email kind. */
export type TrustBadge = 'phone' | EmailVerificationType;

export interface VerifiedItemDTO {
  verification_type: EmailVerificationType | string;
  email_domain?: string | null;
  verified_at?: string | null;
}

export interface PendingEmailCodeDTO {
  verification_type: EmailVerificationType | string;
  email_domain: string;
  expires_at: string;
}

export interface UserTrustStatusDTO {
  user_id: string;
  total_trust_score: number; // 0 to 100
  badges: (TrustBadge | string)[];
  /** Mobile number and a work or college email both verified. */
  is_fully_verified: boolean;
  phone_verified?: boolean;
  verifications?: VerifiedItemDTO[];
  pending?: PendingEmailCodeDTO | null;
  id_verification_available?: boolean;
}

export interface SendEmailCodeRequest {
  verification_type: EmailVerificationType;
  email: string;
}

export interface SendEmailCodeResponse {
  success: boolean;
  message: string;
  email_domain: string;
  already_verified?: boolean;
  expires_in?: number;
  resend_after?: number;
  /** Development servers only. */
  dev_code?: string;
}

export interface ReportCreateInput {
  target_type: 'user' | 'property' | 'message' | string;
  target_id: string;
  reason: string;
  description?: string;
}

export interface ReportDTO {
  id: string;
  reporter_id: string;
  target_type: string;
  target_id: string;
  reason: string;
  description?: string | null;
  status: string;
  created_at: string;
}

export interface BlockUserDTO {
  id: string;
  user_id: string;
  blocked_user_id: string;
  created_at: string;
}
