"use client";

import React, { useState } from "react";
import { Button, Input, Modal } from "@flatmate/ui";
import { CheckCircle2, MapPin, Video } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { localDateInputValue } from "@/lib/utils";
import { InlineNotice } from "@/components/states/InlineNotice";

interface VisitModalProps {
  isOpen: boolean;
  onClose: () => void;
  propertyId: string;
  hostId: string;
  roomId: string | null;
}

/**
 * Book an in-person visit or a video tour. The chosen date and time are the user's local time
 * (the browser converts them to UTC); they used to be sent as if they were UTC, which shifted an
 * 11:00 IST request to 16:30 IST.
 */
export function VisitModal({ isOpen, onClose, propertyId, hostId, roomId }: VisitModalProps) {
  const [today] = useState(() => localDateInputValue());
  const [type, setType] = useState<"physical_visit" | "video_call">("physical_visit");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("11:00");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const scheduled = new Date(`${date}T${time}:00`);
    if (Number.isNaN(scheduled.getTime()) || scheduled.getTime() <= Date.now()) {
      setError("Pick a date and time in the future.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await apiClient("/appointments/", {
        method: "POST",
        body: JSON.stringify({
          property_id: propertyId,
          room_id: roomId || undefined,
          host_id: hostId,
          appointment_type: type,
          scheduled_at: scheduled.toISOString(),
          notes: notes || undefined,
        }),
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to book the visit");
    } finally {
      setIsSubmitting(false);
    }
  };

  const typeButton = (value: "physical_visit" | "video_call", label: string, Icon: typeof MapPin) => (
    <button
      type="button"
      onClick={() => setType(value)}
      aria-pressed={type === value}
      className={`min-h-[44px] px-3 text-xs font-semibold rounded-xl border flex items-center justify-center gap-1.5 transition-all ${
        type === value ? "bg-pale-green/40 border-forest text-forest shadow-2xs" : "border-slate-200 text-charcoal hover:bg-slate-50"
      }`}
    >
      <Icon className="w-3.5 h-3.5" />
      <span>{label}</span>
    </button>
  );

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Book a viewing" description="Visit in person or take a video tour with the host.">
      {done ? (
        <div className="text-center py-6">
          <CheckCircle2 className="w-12 h-12 text-forest mx-auto mb-2" />
          <h3 className="font-bold text-charcoal text-base">Visit requested</h3>
          <p className="text-xs text-charcoal-muted mt-1">
            The host will confirm the time. Exact directions unlock once it&apos;s confirmed.
          </p>
          <Button variant="ghost" className="mt-4 min-h-[44px]" onClick={onClose}>Close</Button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          {error && <InlineNotice tone="error">{error}</InlineNotice>}
          <fieldset>
            <legend className="block text-xs font-semibold text-charcoal mb-1.5">Type of visit</legend>
            <div className="grid grid-cols-2 gap-2">
              {typeButton("physical_visit", "In person", MapPin)}
              {typeButton("video_call", "Video call", Video)}
            </div>
          </fieldset>
          <div className="grid grid-cols-1 min-[400px]:grid-cols-2 gap-3">
            <Input label="Date" type="date" min={today} required value={date} onChange={(e) => setDate(e.target.value)} />
            <Input label="Time (your local time)" type="time" required value={time} onChange={(e) => setTime(e.target.value)} />
          </div>
          <div>
            <label htmlFor="visit-notes" className="block text-xs font-semibold text-charcoal mb-1">Notes for the host (optional)</label>
            <textarea
              id="visit-notes"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. I'd like to check the kitchen and power backup."
              className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-forest"
            />
          </div>
          <Button type="submit" variant="primary" className="w-full mt-2 min-h-[44px]" isLoading={isSubmitting}>
            Request visit
          </Button>
        </form>
      )}
    </Modal>
  );
}
