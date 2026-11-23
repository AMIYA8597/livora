"use client";

import React, { useState } from "react";
import type { ProfileDTO } from "@flatmate/contracts";
import { Button, Card, Input } from "@flatmate/ui";
import { apiClient } from "@/lib/api-client";
import { InlineNotice } from "@/components/states/InlineNotice";

interface ProfileDetailsFormProps {
  /** Saved profile, or null before the first save. Remount with a new `key` to reload it. */
  initial: ProfileDTO | null;
  onSaved?: (profile: ProfileDTO) => void;
}

/** Public profile basics: name, bio, occupation, budget and preferred localities. */
export function ProfileDetailsForm({ initial, onSaved }: ProfileDetailsFormProps) {
  const [displayName, setDisplayName] = useState(initial?.display_name ?? "");
  const [bio, setBio] = useState(initial?.bio ?? "");
  const [occupation, setOccupation] = useState(initial?.occupation || initial?.designation || "");
  const [budgetMin, setBudgetMin] = useState(String(initial?.budget_min ?? 10000));
  const [budgetMax, setBudgetMax] = useState(String(initial?.budget_max ?? 25000));
  const [preferredLocations, setPreferredLocations] = useState((initial?.preferred_locations ?? []).join(", "));
  const [isSaving, setIsSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const min = parseInt(budgetMin, 10);
    const max = parseInt(budgetMax, 10);
    if (Number.isFinite(min) && Number.isFinite(max) && min > max) {
      setNotice({ tone: "error", text: "Minimum budget can't be more than the maximum." });
      return;
    }
    setIsSaving(true);
    setNotice(null);
    try {
      const updated = await apiClient<ProfileDTO>("/profiles/me", {
        method: "PUT",
        body: JSON.stringify({
          display_name: displayName,
          bio,
          occupation,
          budget_min: min,
          budget_max: max,
          preferred_locations: preferredLocations.split(",").map((s) => s.trim()).filter(Boolean),
        }),
      });
      onSaved?.(updated);
      setNotice({ tone: "success", text: "Profile details saved." });
    } catch (err) {
      setNotice({ tone: "error", text: err instanceof Error ? err.message : "Failed to update profile" });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="p-6 max-w-2xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-charcoal">Public profile</h2>
        <p className="text-xs text-charcoal-muted mt-1">
          Visible to other room seekers and landlords looking for flatmates.
        </p>
      </div>

      {notice && <InlineNotice tone={notice.tone} className="mb-4">{notice.text}</InlineNotice>}

      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Display name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="e.g. Rahul Sharma"
          required
        />

        <div>
          <label htmlFor="profile-bio" className="block text-xs font-semibold text-charcoal mb-1">
            About me
          </label>
          <textarea
            id="profile-bio"
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            rows={3}
            className="w-full text-sm rounded-xl border border-slate-200 p-2.5 focus:ring-2 focus:ring-forest focus:outline-none"
            placeholder="Your work, routine and roommate vibe…"
          />
        </div>

        <Input
          label="Occupation / designation"
          value={occupation}
          onChange={(e) => setOccupation(e.target.value)}
          placeholder="e.g. Product Designer"
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input
            label="Min monthly budget (₹)"
            type="number"
            inputMode="numeric"
            min={0}
            value={budgetMin}
            onChange={(e) => setBudgetMin(e.target.value)}
          />
          <Input
            label="Max monthly budget (₹)"
            type="number"
            inputMode="numeric"
            min={0}
            value={budgetMax}
            onChange={(e) => setBudgetMax(e.target.value)}
          />
        </div>

        <Input
          label="Preferred localities (comma separated)"
          value={preferredLocations}
          onChange={(e) => setPreferredLocations(e.target.value)}
          placeholder="e.g. Koramangala, Indiranagar, HSR Layout"
        />

        <Button type="submit" variant="primary" isLoading={isSaving} className="w-full sm:w-auto">
          Save profile
        </Button>
      </form>
    </Card>
  );
}
