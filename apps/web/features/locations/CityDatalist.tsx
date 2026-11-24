"use client";

import React from "react";
import type { CityDTO } from "@flatmate/contracts";
import { citySuggestions } from "@/lib/locations";

/**
 * Suggestions for a free-text city box (`<input list={id}>`): every catalogue city and the other
 * names people type, like "Bangalore". The box still accepts localities and anything else.
 */
export function CityDatalist({ id, cities }: { id: string; cities: CityDTO[] }) {
  return (
    <datalist id={id}>
      {citySuggestions(cities).map((name) => (
        <option key={name} value={name} />
      ))}
    </datalist>
  );
}
