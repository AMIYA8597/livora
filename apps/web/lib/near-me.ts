/**
 * "Near me" search: the browser's position, asked for only when the visitor taps the button,
 * rounded to about 1 km before it leaves the device, kept in memory and never saved. Pure helpers
 * here so they can be unit-tested with `node --test`.
 */

export interface NearPoint {
  lat: number;
  lng: number;
}

/** Radius choices (km) and the default. */
export const RADIUS_CHOICES = [2, 5, 10, 25, 50] as const;
export const DEFAULT_RADIUS_KM = 10;

/** Two decimals is about 1.1 km: plenty for "rooms near me", too coarse to pinpoint a home. */
export function roundPoint(latitude: number, longitude: number): NearPoint {
  const r = (x: number) => Math.round(x * 100) / 100;
  return { lat: r(latitude), lng: r(longitude) };
}

/** The listing query's near-point parameters, or none when "near me" is off. */
export function nearParams(near: NearPoint | null, radiusKm: number) {
  if (!near) return {};
  return { near_lat: near.lat, near_lng: near.lng, radius_km: radiusKm };
}

/** "Under 1 km away", "2.4 km away", "18 km away". */
export function formatDistance(km: number | null | undefined): string | null {
  if (km === null || km === undefined || !Number.isFinite(km)) return null;
  if (km < 1) return "Under 1 km away";
  if (km < 10) return `${km.toFixed(1)} km away`;
  return `${Math.round(km)} km away`;
}

/** What to tell the visitor when the browser can't give a position (GeolocationPositionError codes). */
export function locationErrorMessage(code: number | "unsupported"): string {
  switch (code) {
    case 1:
      return "Location is blocked for this site. Allow it in your browser's site settings, or choose a city instead.";
    case 2:
      return "Your location isn't available right now. Check that location services are on, or choose a city.";
    case 3:
      return "Finding your location took too long. Try again, or choose a city.";
    default:
      return "This browser can't share your location. Choose a city instead.";
  }
}
