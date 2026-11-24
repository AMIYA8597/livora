export type PropertyCategory = 'apartment' | 'independent_house' | 'pg' | 'hostel' | 'co_living' | 'villa';
export type PropertyConfiguration = '1RK' | '1BHK' | '2RK' | '2BHK' | '3BHK' | '4BHK_plus' | 'studio';
export type PropertyType = PropertyCategory | 'house' | 'condo' | 'townhouse'; // Backward compatible alias
export type RoomType = 'private' | 'shared' | '2_sharing' | '3_sharing' | 'master_ensuite';
export type FurnishingStatus = 'fully_furnished' | 'semi_furnished' | 'unfurnished';
export type ListingStatus = 'draft' | 'pending_verification' | 'published' | 'paused' | 'archived';

export interface BedDTO {
  id: string;
  room_id: string;
  bed_identifier: string;
  monthly_rent: number;
  available_from: string;
  is_occupied: boolean;
  current_occupant_id?: string | null;
}

export interface RoomDTO {
  id: string;
  property_id: string;
  room_name: string;
  room_type: RoomType;
  room_rent: number;
  deposit: number;
  private_bath: boolean;
  attached_balcony?: boolean;
  max_beds?: number;
  occupied_beds?: number;
  is_available: boolean;
  available_from: string;
  beds?: BedDTO[];
  created_at?: string;
}

export interface FuzzedCoordinatesDTO {
  lat: number;
  lng: number;
  precision_level: string;
}

export interface PropertyDTO {
  id: string;
  owner_id: string;
  title: string;
  description: string;
  property_type?: PropertyType;
  property_category?: PropertyCategory;
  configuration?: PropertyConfiguration;
  latitude: number;
  longitude: number;
  fuzzed_coordinates?: FuzzedCoordinatesDTO;
  /** Only in near-me searches: km from the searcher to the listing's shown position. */
  distance_km?: number | null;
  address?: string;
  address_display?: string;
  address_exact?: string;
  city: string;
  state?: string | null;
  postal_code: string;
  country: string;
  currency?: string;
  monthly_rent: number;
  deposit?: number;
  security_deposit?: number;
  maintenance_monthly?: number;
  bills_included: boolean;
  total_bedrooms: number;
  total_bathrooms: number;
  max_capacity?: number;
  current_occupants?: number;
  available_from: string;
  is_furnished: boolean;
  furnishing_status?: FurnishingStatus;
  pets_allowed: boolean;
  smoking_allowed: boolean;
  is_verified?: boolean;
  /** Owner Pro: shown first in search while featured. */
  is_featured?: boolean;
  listing_status?: ListingStatus;
  images: string[];
  amenities: string[];
  rooms: RoomDTO[];
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface PropertyCreateInput {
  title: string;
  description: string;
  property_category?: PropertyCategory;
  configuration?: PropertyConfiguration;
  property_type?: PropertyType;
  latitude: number;
  longitude: number;
  address_display?: string;
  address_exact?: string;
  address?: string;
  city: string;
  state?: string;
  postal_code: string;
  country?: string;
  currency?: string;
  monthly_rent: number;
  security_deposit?: number;
  deposit?: number;
  maintenance_monthly?: number;
  bills_included?: boolean;
  total_bedrooms: number;
  total_bathrooms: number;
  max_capacity?: number;
  available_from: string;
  is_furnished?: boolean;
  furnishing_status?: FurnishingStatus;
  pets_allowed?: boolean;
  smoking_allowed?: boolean;
  images?: string[];
  amenities?: string[];
  rooms?: Array<{
    room_name: string;
    room_type: string;
    room_rent: number;
    deposit?: number;
    private_bath?: boolean;
    attached_balcony?: boolean;
    max_beds?: number;
    available_from: string;
    beds?: Array<{
      bed_identifier: string;
      monthly_rent: number;
      available_from: string;
    }>;
  }>;
}

export interface PropertySearchQuery {
  city?: string;
  min_rent?: number;
  max_rent?: number;
  bedrooms?: number;
  configuration?: PropertyConfiguration;
  property_category?: PropertyCategory;
  is_furnished?: boolean;
  furnishing_status?: FurnishingStatus;
  pets_allowed?: boolean;
  available_from?: string;
  lat?: number;
  lng?: number;
  radius_km?: number;
  page?: number;
  limit?: number;
  offset?: number;
}

export interface ListingStatusUpdate {
  listing_status: ListingStatus;
}

export interface AssignOccupantRequest {
  occupant_id: string;
}
