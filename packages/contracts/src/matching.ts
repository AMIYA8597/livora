import { ProfileDTO } from './profile';
import { PropertyDTO } from './property';

export interface ScoreBreakdown {
  overall_score: number;        // 0 to 100
  lifestyle_score: number;      // 0 to 100 (cosine vector similarity)
  cleanliness_alignment: number; // 0 to 100
  schedule_alignment: number;    // 0 to 100
  social_alignment: number;      // 0 to 100
  budget_alignment: number;      // 0 to 100
  dealbreakers_cleared: boolean;
  shared_interests: string[];
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
