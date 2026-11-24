export interface OwnerBed {
  id: string;
  bed_identifier: string;
  monthly_rent: number;
  is_occupied: boolean;
  current_occupant_id?: string | null;
}

export interface OwnerRoom {
  id: string;
  room_name: string;
  room_type: string;
  room_rent: number;
  deposit: number;
  private_bath: boolean;
  beds: OwnerBed[];
}

export interface OwnerProperty {
  id: string;
  title: string;
  description: string;
  property_category: string;
  configuration: string;
  address_display: string;
  city: string;
  monthly_rent: number;
  security_deposit: number;
  listing_status: string;
  is_featured?: boolean;
  is_verified: boolean;
  is_active: boolean;
  rooms: OwnerRoom[];
}

/** `/owners/applications` returns either a nested `application` or flat fields, depending on version. */
export interface OwnerApplicantCard {
  application?: {
    id: string;
    proposed_rent: number;
    move_in_target: string;
    status: string;
    introduction?: string;
  };
  application_id?: string;
  applicant_name: string;
  applicant_email: string;
  applicant_occupation?: string | null;
  property_title: string;
  proposed_rent?: number;
  move_in_target?: string;
  status?: string;
}

export interface OwnerApplication {
  id: string;
  status: string;
  proposedRent: number;
  moveIn: string;
  introduction?: string;
  applicantName: string;
  applicantOccupation?: string | null;
  propertyTitle: string;
}

export function normalizeApplication(card: OwnerApplicantCard): OwnerApplication {
  return {
    id: card.application?.id || card.application_id || "",
    status: card.application?.status || card.status || "submitted",
    proposedRent: card.application?.proposed_rent || card.proposed_rent || 0,
    moveIn: card.application?.move_in_target || card.move_in_target || "",
    introduction: card.application?.introduction,
    applicantName: card.applicant_name,
    applicantOccupation: card.applicant_occupation,
    propertyTitle: card.property_title,
  };
}

export interface OwnerAppointment {
  id: string;
  property_id: string;
  applicant_id: string;
  host_id: string;
  scheduled_at: string;
  status: string;
  notes?: string;
}

export interface OwnerStatsData {
  total_properties?: number;
  active_listings?: number;
  pending_applications?: number;
  estimated_monthly_revenue?: number | string;
}
