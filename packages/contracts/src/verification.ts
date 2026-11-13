export type VerificationType = 'government_id' | 'student_email' | 'work_email' | 'background_check';
export type VerificationStatus = 'pending' | 'approved' | 'rejected';

export interface VerificationDTO {
  id: string;
  user_id: string;
  verification_type: VerificationType;
  status: VerificationStatus;
  document_url?: string | null;
  trust_score_bonus: number;
  verified_at?: string | null;
  created_at: string;
}

export interface UserTrustStatusDTO {
  user_id: string;
  total_trust_score: number; // 0 to 100
  badges: VerificationType[];
  is_fully_verified: boolean;
}
