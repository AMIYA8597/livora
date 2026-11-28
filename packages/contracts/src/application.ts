export type ApplicationStatus = 'draft' | 'submitted' | 'reviewing' | 'accepted' | 'rejected' | 'withdrawn';

export interface ApplicationDTO {
  id: string;
  applicant_id: string;
  group_id?: string | null;
  property_id: string;
  room_id?: string | null;
  status: ApplicationStatus | string;
  introduction: string;
  proposed_rent: number;
  move_in_target: string;
  documents: string[];
  submitted_at: string;
  updated_at: string;
  /** In the applicant's own list (GET /applications/me): the listing it is for. */
  property_title?: string | null;
  property_city?: string | null;
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
  status: ApplicationStatus | string;
  note?: string;
}

/** One entry of GET /applications/{id}/history, as the applicant and the owner see it. */
export interface ApplicationTimelineEntryDTO {
  /** Null for the submission itself. */
  from_status: string | null;
  to_status: string;
  /** A role, never a name: staff changes show as "support", and staff reasons stay with staff. */
  actor: "applicant" | "owner" | "support" | "unknown";
  created_at: string;
}

export type AppointmentType = 'physical_visit' | 'video_call';
export type AppointmentStatus = 'pending' | 'confirmed' | 'completed' | 'cancelled' | 'rescheduled';

export interface AppointmentDTO {
  id: string;
  property_id: string;
  room_id?: string | null;
  applicant_id: string;
  host_id: string;
  appointment_type: AppointmentType | string;
  scheduled_at: string;
  meeting_link?: string | null;
  notes?: string | null;
  status: AppointmentStatus | string;
  cancellation_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AppointmentCreateInput {
  property_id: string;
  room_id?: string;
  host_id: string;
  appointment_type?: AppointmentType | string;
  scheduled_at: string;
  meeting_link?: string;
  notes?: string;
}

export interface AppointmentStatusUpdateInput {
  status: AppointmentStatus | string;
  cancellation_reason?: string;
}
