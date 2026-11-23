import React from "react";
import { Input } from "@flatmate/ui";
import type { SmokingPolicy } from "../draft";
import { CheckboxField, SelectField, type StepProps } from "./fields";

const AMENITIES = ["wifi", "power_backup", "lift", "security", "parking", "geyser", "air_conditioner", "washing_machine"];

export function PricingStep({ draft, update }: StepProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Input
        label="Rent for the whole place (₹/month)"
        type="number"
        inputMode="numeric"
        min={1}
        value={draft.monthlyRent}
        onChange={(e) => update({ monthlyRent: e.target.value })}
      />
      <Input
        label="Security deposit (₹)"
        type="number"
        inputMode="numeric"
        min={0}
        value={draft.deposit}
        onChange={(e) => update({ deposit: e.target.value })}
      />
      <Input
        label="Maintenance (₹/month)"
        type="number"
        inputMode="numeric"
        min={0}
        value={draft.maintenance}
        onChange={(e) => update({ maintenance: e.target.value })}
      />
      <div className="md:pt-5">
        <CheckboxField
          id="listing-bills"
          label="Water, electricity and gas included in rent"
          checked={draft.billsIncluded}
          onChange={(billsIncluded) => update({ billsIncluded })}
        />
      </div>
    </div>
  );
}

export function AmenitiesStep({ draft, update }: StepProps) {
  const toggle = (a: string) =>
    update({ amenities: draft.amenities.includes(a) ? draft.amenities.filter((x) => x !== a) : [...draft.amenities, a] });
  return (
    <div className="space-y-5">
      <fieldset>
        <legend className="block text-xs font-semibold text-charcoal mb-2">Amenities</legend>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {AMENITIES.map((a) => {
            const on = draft.amenities.includes(a);
            return (
              <button
                key={a}
                type="button"
                aria-pressed={on}
                onClick={() => toggle(a)}
                className={`min-h-[44px] px-3 rounded-xl border text-xs font-medium text-left capitalize transition-colors ${
                  on ? "bg-pale-green/40 border-forest text-forest" : "border-slate-200 text-charcoal hover:bg-slate-50"
                }`}
              >
                {a.replace(/_/g, " ")}
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3 border-t border-slate-100">
        <SelectField
          id="listing-smoking"
          label="Smoking"
          value={draft.smoking}
          onChange={(smoking) => update({ smoking: smoking as SmokingPolicy })}
          options={[
            { value: "never", label: "No smoking" },
            { value: "balcony_only", label: "Balcony or outdoors only" },
            { value: "permitted", label: "Smoking allowed" },
          ]}
        />
        <div className="sm:pt-5">
          <CheckboxField id="listing-pets" label="Pets allowed" checked={draft.petsAllowed} onChange={(petsAllowed) => update({ petsAllowed })} />
        </div>
      </div>
    </div>
  );
}
