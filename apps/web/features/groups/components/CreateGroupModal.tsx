"use client";

import React, { useState } from "react";
import { Button, Input, Modal } from "@flatmate/ui";
import { apiClient } from "@/lib/api-client";
import { localDateInputValue } from "@/lib/utils";
import { InlineNotice } from "@/components/states/InlineNotice";
import { CityDatalist } from "@/features/locations/CityDatalist";
import { useCities } from "@/hooks/useCities";

interface CreateGroupModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: () => void;
}

/** Mount with a fresh `key` per opening so the form starts clean. */
export function CreateGroupModal({ isOpen, onClose, onCreated }: CreateGroupModalProps) {
  const [today] = useState(() => localDateInputValue());
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [city, setCity] = useState("Bengaluru");
  const { cities } = useCities();
  const [budget, setBudget] = useState("50000");
  const [moveIn, setMoveIn] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await apiClient("/groups/", {
        method: "POST",
        body: JSON.stringify({
          name,
          description,
          target_city: city,
          target_budget_total: parseInt(budget, 10),
          target_move_in: moveIn || undefined,
        }),
      });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create the group");
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Start a group"
      description="Team up with other seekers to pool a budget, shortlist flats and vote together."
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-2">
        {error && <InlineNotice tone="error">{error}</InlineNotice>}
        <Input
          label="Group name"
          required
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. HSR Layout 3BHK seekers"
        />
        <div>
          <label htmlFor="group-description" className="block text-xs font-semibold text-charcoal mb-1">
            What you&apos;re looking for
          </label>
          <textarea
            id="group-description"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Type of flat, area, quiet hours, lifestyle expectations…"
            className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-forest"
          />
        </div>
        <div className="grid grid-cols-1 min-[400px]:grid-cols-2 gap-3">
          <Input label="City" required list="group-city-suggestions" value={city} onChange={(e) => setCity(e.target.value)} />
          <CityDatalist id="group-city-suggestions" cities={cities} />
          <Input
            label="Combined budget (₹/month)"
            type="number"
            inputMode="numeric"
            min={1}
            required
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
          />
        </div>
        <Input label="Target move-in date" type="date" min={today} value={moveIn} onChange={(e) => setMoveIn(e.target.value)} />
        <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSubmitting}>
          Create group
        </Button>
      </form>
    </Modal>
  );
}
