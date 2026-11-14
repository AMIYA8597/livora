import { UserDTO } from './auth';

export type GroupMemberRole = 'leader' | 'member' | 'pending';

export interface GroupMemberDTO {
  id: string;
  group_id: string;
  user_id: string;
  user?: UserDTO;
  role: GroupMemberRole | string;
  joined_at: string;
}

export interface GroupWishlistItemDTO {
  id: string;
  group_id: string;
  property_id: string;
  added_by: string;
  votes: Record<string, 'up' | 'down' | 'neutral' | string>;
  created_at: string;
}

export interface GroupDTO {
  id: string;
  creator_id: string;
  name: string;
  description?: string | null;
  target_budget_total: number;
  target_city: string;
  target_move_in?: string | null;
  members: GroupMemberDTO[];
  wishlist?: GroupWishlistItemDTO[];
  wishlist_items?: GroupWishlistItemDTO[];
  created_at: string;
  updated_at?: string;
}

export interface GroupCreateInput {
  name: string;
  description?: string;
  target_budget_total: number;
  target_city: string;
  target_move_in?: string;
}

export interface AddMemberRequest {
  user_id: string;
  role?: string;
}

export interface WishlistVoteRequest {
  vote: 'up' | 'down' | 'neutral';
}

export interface PairwiseScoreItem {
  user_one_id: string;
  user_one_name: string;
  user_two_id: string;
  user_two_name: string;
  score: number;
  dealbreakers_cleared: boolean;
  conflict_summary?: string | null;
}

export interface GroupCompatibilityResponse {
  group_id: string;
  total_members: number;
  collective_score: number;
  dealbreakers_cleared: boolean;
  pairwise_breakdowns: PairwiseScoreItem[];
  group_conflicts: string[];
  shared_strengths: string[];
}
