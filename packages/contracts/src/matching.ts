import { ProfileDTO } from './profile';
import { PropertyDTO } from './property';

export interface FactorDetail {
  score: number; // 0 to 100
  weight: number;
  explanation: string;
}

export interface CompatibilityReportDTO {
  overall_score: number; // 0 to 100
  dealbreakers_cleared: boolean;
  active_dealbreakers: string[];
  dimensions?: {
    cleanliness?: FactorDetail;
    sleep_schedule?: FactorDetail;
    work_style?: FactorDetail;
    diet?: FactorDetail;
    smoking?: FactorDetail;
    drinking?: FactorDetail;
    social?: FactorDetail;
    guests?: FactorDetail;
    budget?: FactorDetail;
    location?: FactorDetail;
    [key: string]: FactorDetail | undefined;
  };
  explanations?: Record<string, string>;
}

export interface ScoreBreakdown {
  overall_score: number; // 0 to 100
  lifestyle_score?: number; // 0 to 100 (cosine vector similarity)
  cleanliness_alignment?: number; // 0 to 100
  schedule_alignment?: number; // 0 to 100
  social_alignment?: number; // 0 to 100
  budget_alignment?: number; // 0 to 100
  dealbreakers_cleared: boolean;
  shared_interests?: string[];
  factors?: Record<string, number>;
  explanations?: Record<string, string>;
  conflicts?: string[];
  algorithm_version?: string;
  report?: CompatibilityReportDTO;
}

export interface FlatmateMatchRecommendation {
  profile: ProfileDTO;
  match_score: ScoreBreakdown;
}

export interface PropertyMatchRecommendation {
  property: PropertyDTO;
  compatibility_score: number;
  reason: string;
}

export type InteractionAction = 'like' | 'pass' | 'save' | 'super_like';

export interface MatchInteractionRequest {
  target_user_id: string;
  action: InteractionAction;
}

export interface MatchInteractionResponse {
  interaction_id: string;
  user_id: string;
  target_user_id: string;
  action: string;
  is_mutual_match: boolean;
  mutual_match_id?: string | null;
  compatibility_score?: number | null;
}

export interface MutualMatchItemResponse {
  id: string;
  partner_id: string;
  partner_name: string;
  partner_avatar?: string | null;
  partner_occupation?: string | null;
  compatibility_score: number;
  algorithm_version: string;
  score_breakdown: Record<string, any>;
  status: string;
}

export interface MatchInteractionDTO {
  id: string;
  user_id: string;
  target_user_id: string;
  interaction_type: 'like' | 'pass' | 'superlike' | 'save';
  is_mutual_match: boolean;
  created_at: string;
}

export interface MutualMatchDTO {
  id: string;
  user_a_id: string;
  user_b_id: string;
  compatibility_score: number;
  matched_at: string;
  conversation_id?: string | null;
}
