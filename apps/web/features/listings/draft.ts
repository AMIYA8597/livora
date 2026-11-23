/**
 * Listing wizard model: the draft, per-step validation and the API payload. Pure functions with
 * relative imports so they can be unit-tested with `node --test`.
 */
import { cityCentre, SUPPORTED_CITIES } from "../properties/city-centres.ts";

export interface DraftBed {
  id: string;
  identifier: string;
  rent: string;
  occupied: boolean;
}

export interface DraftRoom {
  id: string;
  name: string;
  type: "private" | "shared";
  rent: string;
  deposit: string;
  privateBath: boolean;
  beds: DraftBed[];
}

export type SmokingPolicy = "never" | "balcony_only" | "permitted";

export interface ListingDraft {
  title: string;
  description: string;
  category: string;
  city: string;
  state: string;
  locality: string;
  addressExact: string;
  postalCode: string;
  configuration: string;
  furnishing: string;
  bedrooms: string;
  bathrooms: string;
  capacity: string;
  rooms: DraftRoom[];
  monthlyRent: string;
  deposit: string;
  maintenance: string;
  billsIncluded: boolean;
  amenities: string[];
  smoking: SmokingPolicy;
  petsAllowed: boolean;
  images: string[];
}

export const WIZARD_STEPS = [
  "Basics",
  "Location",
  "Layout",
  "Rooms",
  "Beds",
  "Pricing",
  "Amenities and rules",
  "Photos",
  "Review",
] as const;

let seq = 0;
/** Local-only ids for list keys; never sent to the API. */
export const newId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(seq++).toString(36)}`;

export function newBed(identifier: string, rent = ""): DraftBed {
  return { id: newId("bed"), identifier, rent, occupied: false };
}

export function newRoom(index: number): DraftRoom {
  return { id: newId("room"), name: `Bedroom ${index}`, type: "private", rent: "", deposit: "", privateBath: false, beds: [newBed("Bed A")] };
}

/** Starts empty on purpose: pre-filled sample values were easy to publish by accident. */
export function initialDraft(): ListingDraft {
  return {
    title: "",
    description: "",
    category: "apartment",
    city: "",
    state: "",
    locality: "",
    addressExact: "",
    postalCode: "",
    configuration: "2BHK",
    furnishing: "semi_furnished",
    bedrooms: "2",
    bathrooms: "1",
    capacity: "2",
    rooms: [newRoom(1)],
    monthlyRent: "",
    deposit: "",
    maintenance: "0",
    billsIncluded: false,
    amenities: [],
    smoking: "never",
    petsAllowed: false,
    images: [],
  };
}

const num = (v: string) => (v.trim() === "" ? NaN : Number(v));
const isWhole = (v: string, min: number) => Number.isInteger(num(v)) && num(v) >= min;
const isAmount = (v: string, min: number) => Number.isFinite(num(v)) && num(v) >= min;

/** Returns the first problem on this step (0-based), or null when the user may continue. */
export function validateStep(step: number, d: ListingDraft): string | null {
  switch (step) {
    case 0:
      if (d.title.trim() && d.title.trim().length < 10) return "Make the title at least 10 characters, or leave it blank.";
      return null;
    case 1:
      if (!SUPPORTED_CITIES.includes(d.city)) return "Choose the city.";
      if (!d.locality.trim()) return "Enter the locality or area.";
      if (!/^\d{6}$/.test(d.postalCode.trim())) return "Enter the 6-digit PIN code.";
      return null;
    case 2:
      if (!isWhole(d.bedrooms, 0)) return "Bedrooms must be a whole number.";
      if (!isWhole(d.bathrooms, 1)) return "There must be at least one bathroom.";
      if (!isWhole(d.capacity, 1)) return "Maximum occupancy must be at least 1.";
      return null;
    case 3:
      for (const r of d.rooms) {
        if (!r.name.trim()) return "Every room needs a name.";
        if (!isAmount(r.rent, 1)) return `Enter the monthly rent for ${r.name || "each room"}.`;
        if (r.deposit.trim() && !isAmount(r.deposit, 0)) return `The deposit for ${r.name} must be a number.`;
      }
      return null;
    case 4:
      for (const r of d.rooms) {
        if (r.beds.length === 0) return `${r.name} needs at least one bed.`;
        for (const b of r.beds) {
          if (!b.identifier.trim()) return `Name every bed in ${r.name}.`;
          if (b.rent.trim() && !isAmount(b.rent, 0)) return `Bed rents in ${r.name} must be numbers.`;
        }
      }
      return null;
    case 5:
      if (!isAmount(d.monthlyRent, 1)) return "Enter the monthly rent for the whole place.";
      if (!isAmount(d.deposit, 0)) return "Enter the security deposit (0 if none).";
      if (!isAmount(d.maintenance, 0)) return "Maintenance must be a number (0 if none).";
      return null;
    default:
      return null;
  }
}

/** First step that fails validation, so publishing can jump the user straight to it. */
export function firstInvalidStep(d: ListingDraft): { step: number; message: string } | null {
  for (let s = 0; s < WIZARD_STEPS.length; s++) {
    const message = validateStep(s, d);
    if (message) return { step: s, message };
  }
  return null;
}

export function displayTitle(d: ListingDraft): string {
  return d.title.trim() || `${d.configuration.replace("_plus", "+")} in ${d.locality.trim()}, ${d.city}`;
}

/** The POST /properties body. `today` is the local YYYY-MM-DD date. */
export function buildListingPayload(d: ListingDraft, today: string) {
  const location = `${d.locality.trim()}, ${d.city}`;
  return {
    title: displayTitle(d),
    description: d.description.trim() || `${d.configuration} in ${location}.`,
    property_category: d.category,
    configuration: d.configuration,
    // City-level position until address geocoding exists (the exact address stays private anyway).
    ...cityCentre(d.city),
    address_display: location,
    address_exact: d.addressExact.trim() || location,
    city: d.city,
    state: d.state,
    postal_code: d.postalCode.trim(),
    country: "India",
    currency: "INR",
    monthly_rent: num(d.monthlyRent),
    security_deposit: num(d.deposit),
    maintenance_monthly: num(d.maintenance),
    bills_included: d.billsIncluded,
    total_bedrooms: num(d.bedrooms),
    total_bathrooms: num(d.bathrooms),
    max_capacity: num(d.capacity),
    current_occupants: d.rooms.reduce((n, r) => n + r.beds.filter((b) => b.occupied).length, 0),
    available_from: today,
    is_furnished: d.furnishing !== "unfurnished",
    furnishing_status: d.furnishing,
    pets_allowed: d.petsAllowed,
    smoking_allowed: d.smoking === "permitted",
    images: d.images,
    amenities: d.amenities,
    rooms: d.rooms.map((r) => {
      const roomRent = num(r.rent);
      const share = Math.round(roomRent / Math.max(1, r.beds.length));
      return {
        room_name: r.name.trim(),
        room_type: r.type === "shared" ? `${Math.max(2, r.beds.length)}_sharing` : "private",
        room_rent: roomRent,
        deposit: r.deposit.trim() ? num(r.deposit) : 0,
        private_bath: r.privateBath,
        max_beds: r.beds.length,
        occupied_beds: r.beds.filter((b) => b.occupied).length,
        is_available: r.beds.some((b) => !b.occupied),
        available_from: today,
        beds: r.beds.map((b) => ({
          bed_identifier: b.identifier.trim(),
          monthly_rent: b.rent.trim() ? num(b.rent) : share,
          available_from: today,
          is_occupied: b.occupied,
        })),
      };
    }),
  };
}
