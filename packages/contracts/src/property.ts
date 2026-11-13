export type PropertyType = 'apartment' | 'house' | 'condo' | 'studio' | 'townhouse';
export type RoomType = 'private' | 'shared' | 'master_ensuite';

export interface RoomDTO {
  id: string;
  property_id: string;
  room_name: string;
  room_type: RoomType;
  room_rent: number;
  deposit: number;
  private_bath: boolean;
  is_available: boolean;
  available_from: string;
}

export interface PropertyDTO {
  id: string;
  owner_id: string;
  title: string;
  description: string;
  property_type: PropertyType;
  latitude: number;
  longitude: number;
  address: string;
  city: string;
  state?: string | null;
  postal_code: string;
  country: string;
  monthly_rent: number;
  deposit: number;
  bills_included: boolean;
  total_bedrooms: number;
  total_bathrooms: number;
  available_from: string;
  is_furnished: boolean;
  pets_allowed: boolean;
  smoking_allowed: boolean;
  images: string[];
  amenities: string[];
  rooms: RoomDTO[];
  is_active: boolean;
  created_at: string;
}

export interface PropertyCreateInput {
  title: string;
  description: string;
  property_type: PropertyType;
  latitude: number;
  longitude: number;
  address: string;
  city: string;
  state?: string;
  postal_code: string;
  monthly_rent: number;
  deposit?: number;
  bills_included?: boolean;
  total_bedrooms: number;
  total_bathrooms: number;
  available_from: string;
  is_furnished?: boolean;
  pets_allowed?: boolean;
  smoking_allowed?: boolean;
  images?: string[];
  amenities?: string[];
}

export interface PropertySearchQuery {
  city?: string;
  min_rent?: number;
  max_rent?: number;
  bedrooms?: number;
  is_furnished?: boolean;
  pets_allowed?: boolean;
  available_from?: string;
  lat?: number;
  lng?: number;
  radius_km?: number;
  page?: number;
  limit?: number;
}
