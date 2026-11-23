/**
 * Approximate city centres for the cities the listing wizard offers. Used as a listing's map
 * position until address geocoding exists: good enough for "near me" search at city level, and
 * the exact address is only revealed after a confirmed visit anyway.
 */
const CENTRES: Record<string, { latitude: number; longitude: number; state: string }> = {
  Bengaluru: { latitude: 12.9716, longitude: 77.5946, state: "Karnataka" },
  Mumbai: { latitude: 19.076, longitude: 72.8777, state: "Maharashtra" },
  "Delhi NCR": { latitude: 28.6139, longitude: 77.209, state: "Delhi" },
  Hyderabad: { latitude: 17.385, longitude: 78.4867, state: "Telangana" },
  Pune: { latitude: 18.5204, longitude: 73.8567, state: "Maharashtra" },
  Chennai: { latitude: 13.0827, longitude: 80.2707, state: "Tamil Nadu" },
};

export const SUPPORTED_CITIES = Object.keys(CENTRES);

export function cityState(city: string): string {
  return CENTRES[city]?.state ?? "";
}

export function cityCentre(city: string): { latitude: number; longitude: number } {
  const centre = CENTRES[city];
  if (!centre) throw new Error(`Choose one of the supported cities (${SUPPORTED_CITIES.join(", ")}).`);
  return { latitude: centre.latitude, longitude: centre.longitude };
}
