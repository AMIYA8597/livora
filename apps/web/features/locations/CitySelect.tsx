"use client";

import React from "react";
import type { CityDTO } from "@flatmate/contracts";
import { cityGroups } from "@/lib/locations";

/**
 * A native select of catalogue cities: popular ones first, then every state and union territory
 * with its cities. The value is the city's official name.
 */
export function CitySelect({
  id,
  cities,
  value,
  onChange,
  placeholder = "Choose a city",
  className,
  ariaLabel,
}: {
  id?: string;
  cities: CityDTO[];
  value: string;
  onChange: (city: CityDTO | undefined) => void;
  placeholder?: string;
  className?: string;
  ariaLabel?: string;
}) {
  const groups = cityGroups(cities);
  return (
    <select
      id={id}
      aria-label={ariaLabel}
      value={value}
      onChange={(e) => onChange(cities.find((c) => c.name === e.target.value))}
      className={className}
    >
      <option value="">{cities.length ? placeholder : "Loading cities…"}</option>
      {groups.map((g) => (
        <optgroup key={g.label} label={g.label}>
          {g.cities.map((c) => (
            <option key={`${g.label}-${c.slug}`} value={c.name}>
              {g.label === "Popular" ? `${c.name} (${c.state})` : c.name}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
