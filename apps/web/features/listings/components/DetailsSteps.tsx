import React from "react";
import { Input } from "@flatmate/ui";
import { CitySelect } from "@/features/locations/CitySelect";
import { useCities } from "@/hooks/useCities";
import { control, SelectField, TextAreaField, type StepProps } from "./fields";

export function BasicsStep({ draft, update }: StepProps) {
  return (
    <div className="space-y-4">
      <Input
        label="Listing title (optional)"
        value={draft.title}
        maxLength={120}
        onChange={(e) => update({ title: e.target.value })}
        placeholder="e.g. Sunny 2BHK near Sony Signal, Koramangala"
      />
      <SelectField
        id="listing-category"
        label="Type of place"
        value={draft.category}
        onChange={(category) => update({ category })}
        options={[
          { value: "apartment", label: "Entire apartment / flat" },
          { value: "independent_house", label: "Independent house / villa" },
          { value: "pg", label: "PG accommodation" },
          { value: "co_living", label: "Co-living space" },
        ]}
      />
      <TextAreaField
        id="listing-description"
        label="Description"
        value={draft.description}
        onChange={(description) => update({ description })}
        placeholder="What's nearby, transport links, who the place suits…"
      />
    </div>
  );
}

export function LocationStep({ draft, update }: StepProps) {
  const { cities, error, retry } = useCities();
  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="listing-city" className="block text-xs font-semibold text-charcoal mb-1">City</label>
        <CitySelect
          id="listing-city"
          cities={cities}
          value={draft.city}
          className={control}
          onChange={(c) =>
            update(
              c && c.latitude != null && c.longitude != null
                ? { city: c.name, state: c.state, centre: { latitude: c.latitude, longitude: c.longitude } }
                : { city: "", state: "", centre: null },
            )
          }
        />
        {error ? (
          <p className="mt-1 text-xs text-red-700">
            Couldn&apos;t load the city list.{" "}
            <button type="button" onClick={retry} className="underline font-semibold">Try again</button>
          </p>
        ) : (
          <p className="mt-1 text-xs text-slate-500">Every state and union territory capital, plus major cities.</p>
        )}
      </div>
      <Input
        label="Locality or area (shown publicly)"
        value={draft.locality}
        onChange={(e) => update({ locality: e.target.value })}
        placeholder="e.g. HSR Layout Sector 4"
      />
      <Input
        label="Exact address (only shared after a confirmed visit)"
        value={draft.addressExact}
        onChange={(e) => update({ addressExact: e.target.value })}
        placeholder="e.g. Flat 302, Green Glen Apartments, 14th Main"
      />
      <Input
        label="PIN code"
        inputMode="numeric"
        autoComplete="postal-code"
        value={draft.postalCode}
        // Strip first, then trim: a native maxLength would cut "411 045" to "411 04".
        onChange={(e) => update({ postalCode: e.target.value.replace(/\D/g, "").slice(0, 6) })}
        placeholder="6 digits"
      />
    </div>
  );
}

export function LayoutStep({ draft, update }: StepProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <SelectField
        id="listing-configuration"
        label="Configuration"
        value={draft.configuration}
        onChange={(configuration) => update({ configuration })}
        options={["1RK", "1BHK", "2BHK", "3BHK", "4BHK_plus", "studio"].map((v) => ({
          value: v,
          label: v === "4BHK_plus" ? "4BHK+" : v === "studio" ? "Studio" : v,
        }))}
      />
      <SelectField
        id="listing-furnishing"
        label="Furnishing"
        value={draft.furnishing}
        onChange={(furnishing) => update({ furnishing })}
        options={[
          { value: "fully_furnished", label: "Fully furnished" },
          { value: "semi_furnished", label: "Semi-furnished" },
          { value: "unfurnished", label: "Unfurnished" },
        ]}
      />
      <Input label="Bedrooms" type="number" inputMode="numeric" min={0} value={draft.bedrooms} onChange={(e) => update({ bedrooms: e.target.value })} />
      <Input label="Bathrooms" type="number" inputMode="numeric" min={1} value={draft.bathrooms} onChange={(e) => update({ bathrooms: e.target.value })} />
      <Input label="Maximum occupants" type="number" inputMode="numeric" min={1} value={draft.capacity} onChange={(e) => update({ capacity: e.target.value })} />
    </div>
  );
}
