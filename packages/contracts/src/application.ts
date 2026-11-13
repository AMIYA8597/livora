export type ApplicationStatus = 'draft' | 'submitted' | 'reviewing' | 'accepted' | 'rejected' | 'withdrawn';

export interface ApplicationDTO {
  id: string;
  applicant_id: string;
  group_id?: string | null;
  property_id: string;
  room_id?: string | null;
  status: ApplicationStatus;
  introduction: string;
  proposed_rent: number;
  move_in_target: string;
  documents: string[];
  submitted_at: string;
  updated_at: string;
}

export interface ApplicationCreateInput {
  property_id: string;
  room_id?: string;
  group_id?: string;
  introduction: string;
  proposed_rent: number;
  move_in_target: string;
  documents?: string[];
}

export interface ApplicationStatusUpdate {
  status: ApplicationStatus;
  note?: string;
}
