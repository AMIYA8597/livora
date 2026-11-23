"use client";

import React, { useState } from "react";
import type { Lifestyle10DimensionDTO } from "@flatmate/contracts";
import { Button, Card } from "@flatmate/ui";
import { Briefcase, Cigarette, Dog, Moon, Users, Utensils, Volume2, DoorOpen } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { InlineNotice } from "@/components/states/InlineNotice";
import {
  DIET_OPTIONS,
  GUEST_OPTIONS,
  LIFESTYLE_DEFAULTS,
  NOISE_OPTIONS,
  type Option,
  PET_OPTIONS,
  SLEEP_OPTIONS,
  SMOKING_OPTIONS,
  SOCIAL_OPTIONS,
  WORK_OPTIONS,
} from "../lifestyle-options";

interface LifestyleFormProps {
  /** Saved answers, or null if the questionnaire was never completed. */
  initial: Lifestyle10DimensionDTO | null;
  onSaved?: (lifestyle: Lifestyle10DimensionDTO) => void;
}

type Answers = typeof LIFESTYLE_DEFAULTS;

function SelectField({
  id, label, icon: Icon, value, options, onChange,
}: {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
}) {
  // A saved value we no longer offer stays selectable rather than being silently replaced.
  const list = options.some((o) => o.value === value) ? options : [...options, { value, label: value.replace(/_/g, " ") }];
  return (
    <div>
      <label htmlFor={id} className="text-xs font-semibold text-charcoal mb-1 flex items-center gap-1.5">
        <Icon className="w-3.5 h-3.5 text-forest" /> {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full min-h-[44px] text-sm rounded-xl border border-slate-200 px-2.5 bg-white focus:ring-2 focus:ring-forest focus:outline-none"
      >
        {list.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

/** The lifestyle questionnaire that feeds compatibility scoring. */
export function LifestyleForm({ initial, onSaved }: LifestyleFormProps) {
  const [answers, setAnswers] = useState<Answers>(() => {
    const merged = { ...LIFESTYLE_DEFAULTS };
    (Object.keys(merged) as (keyof Answers)[]).forEach((k) => {
      const v = initial?.[k];
      if (v !== undefined && v !== null && v !== "") (merged as Record<string, unknown>)[k] = v;
    });
    return merged;
  });
  const [isSaving, setIsSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const set = <K extends keyof Answers>(key: K) => (value: Answers[K]) => setAnswers((a) => ({ ...a, [key]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setNotice(null);
    try {
      // PUT replaces the whole record, so send saved fields this form doesn't show as well.
      const savedRest: Record<string, unknown> = { ...(initial ?? {}) };
      delete savedRest.id;
      delete savedRest.user_id;
      const saved = await apiClient<Lifestyle10DimensionDTO>("/lifestyle/me", {
        method: "PUT",
        body: JSON.stringify({ ...savedRest, ...answers }),
      });
      onSaved?.(saved);
      setNotice({ tone: "success", text: "Lifestyle answers saved. Your matches will update." });
    } catch (err) {
      setNotice({ tone: "error", text: err instanceof Error ? err.message : "Failed to save questionnaire" });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="p-6 max-w-2xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-charcoal">Lifestyle preferences</h2>
        <p className="text-xs text-charcoal-muted mt-1">
          Used to score how well you and a potential flatmate would live together.
        </p>
      </div>

      {notice && <InlineNotice tone={notice.tone} className="mb-4">{notice.text}</InlineNotice>}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <SelectField id="ls-sleep" label="Sleep schedule" icon={Moon} value={answers.sleep_schedule} options={SLEEP_OPTIONS} onChange={set("sleep_schedule")} />
          <SelectField id="ls-work" label="Work arrangement" icon={Briefcase} value={answers.work_arrangement} options={WORK_OPTIONS} onChange={set("work_arrangement")} />
          <SelectField id="ls-diet" label="Food & diet" icon={Utensils} value={answers.diet_preference} options={DIET_OPTIONS} onChange={set("diet_preference")} />
          <SelectField id="ls-smoking" label="Smoking" icon={Cigarette} value={answers.smoking} options={SMOKING_OPTIONS} onChange={set("smoking")} />
          <SelectField id="ls-pets" label="Pets" icon={Dog} value={answers.pet_preference} options={PET_OPTIONS} onChange={set("pet_preference")} />
          <SelectField id="ls-social" label="Social battery" icon={Users} value={answers.social_battery} options={SOCIAL_OPTIONS} onChange={set("social_battery")} />
          <SelectField id="ls-noise" label="Noise tolerance" icon={Volume2} value={answers.noise_tolerance} options={NOISE_OPTIONS} onChange={set("noise_tolerance")} />
          <SelectField id="ls-guests" label="Guests" icon={DoorOpen} value={answers.guests_policy} options={GUEST_OPTIONS} onChange={set("guests_policy")} />
        </div>

        <div>
          <div className="flex justify-between items-center mb-1">
            <label htmlFor="ls-clean" className="text-xs font-semibold text-charcoal">Cleanliness standard</label>
            <span className="text-xs font-bold text-forest">{answers.cleanliness_level} / 5</span>
          </div>
          <input
            id="ls-clean"
            type="range"
            min={1}
            max={5}
            step={1}
            value={answers.cleanliness_level}
            onChange={(e) => set("cleanliness_level")(parseInt(e.target.value, 10))}
            className="w-full accent-forest h-11"
          />
          <div className="flex justify-between text-[11px] text-charcoal-muted">
            <span>Relaxed</span>
            <span>Spotless</span>
          </div>
        </div>

        <Button type="submit" variant="primary" isLoading={isSaving} className="w-full sm:w-auto">
          Save lifestyle answers
        </Button>
      </form>
    </Card>
  );
}
