import { UserDTO } from './auth';

export type GroupMemberRole = 'leader' | 'member' | 'pending';

export interface GroupMemberDTO {
  id: string;
  group_id: string;
  user_id: string;
  user?: UserDTO;
  role: GroupMemberRole;
  joined_at: string;
}

export interface GroupWishlistItemDTO {
  id: string;
  group_id: string;
  property_id: string;
  added_by: string;
  votes: Record<string, 'up' | 'down'>;
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
  created_at: string;
}

export interface GroupCreateInput {
  name: string;
  description?: string;
  target_budget_total: number;
  target_city: string;
  target_move_in?: string;
}
