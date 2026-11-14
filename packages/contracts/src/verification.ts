export type VerificationType = 'government_id' | 'student_email' | 'work_email' | 'background_check';
export type VerificationStatus = 'pending' | 'approved' | 'rejected';

export interface VerificationDTO {
  id: string;
  user_id: string;
  verification_type: VerificationType | string;
  status: VerificationStatus | string;
  document_url?: string | null;
  trust_score_bonus: number;
  verified_at?: string | null;
  created_at: string;
}

export interface SubmitVerificationRequest {
  verification_type: VerificationType | string;
  document_url?: string;
}

export interface UserTrustStatusDTO {
  user_id: string;
  total_trust_score: number; // 0 to 100
  badges: string[];
  is_fully_verified: boolean;
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
