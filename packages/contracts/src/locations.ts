/** GET /locations/cities: a city listings can be in (every state and UT capital, plus major cities). */
export interface CityDTO {
  slug: string;
  name: string;
  state: string;
  state_code: string;
  state_kind: 'state' | 'union_territory';
  is_capital: boolean;
  /** 1 for the large rental markets (shown first), 2 for the rest. */
  tier: number;
  latitude: number | null;
  longitude: number | null;
  /** Other names people search by, e.g. "Bangalore" for Bengaluru. */
  aliases: string[];
}

/** GET /locations/states: India's 28 states and 8 union territories. */
export interface StateDTO {
  code: string;
  name: string;
  kind: 'state' | 'union_territory';
  capital: string | null;
  capital_slug: string | null;
}
