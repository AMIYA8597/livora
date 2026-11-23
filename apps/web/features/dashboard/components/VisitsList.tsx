"use client";

import React from "react";
import { useRouter } from "next/navigation";
import type { AppointmentDTO } from "@flatmate/contracts";
import { Badge, Button, Card, EmptyState } from "@flatmate/ui";
import { Calendar, Clock } from "lucide-react";
import { formatDateTimeIST } from "@/lib/utils";

interface VisitsListProps {
  items: AppointmentDTO[];
  onCancel: (appointmentId: string) => void;
  busyId?: string | null;
}

export function VisitsList({ items, onCancel, busyId }: VisitsListProps) {
  const router = useRouter();
  if (items.length === 0) {
    return (
      <EmptyState
        icon={Calendar}
        title="No visits booked"
        description="Open any listing to book an in-person walkthrough or a video tour."
        actionLabel="Find places to visit"
        onAction={() => router.push("/properties")}
      />
    );
  }
  return (
    <div className="space-y-4">
      {items.map((apt) => {
        const cancellable = apt.status !== "cancelled" && apt.status !== "rejected" && apt.status !== "completed";
        return (
          <Card key={apt.id} className="p-5 border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={apt.appointment_type === "physical_visit" ? "default" : "forest"} size="sm">
                  {apt.appointment_type === "physical_visit" ? "In-person visit" : "Video tour"}
                </Badge>
                <Badge
                  variant={apt.status === "confirmed" ? "success" : apt.status === "cancelled" ? "danger" : "warning"}
                  size="sm"
                  className="capitalize"
                >
                  {apt.status}
                </Badge>
              </div>
              <h3 className="font-semibold text-charcoal text-base mt-1.5 flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-forest" />
                <span>{formatDateTimeIST(apt.scheduled_at)}</span>
              </h3>
              {apt.notes && <p className="text-xs text-charcoal-muted mt-1 break-words">Notes: {apt.notes}</p>}
            </div>
            {cancellable && (
              <Button
                size="sm"
                variant="outline"
                className="min-h-[44px] self-end sm:self-center text-rose-600 border-rose-200 hover:bg-rose-50"
                isLoading={busyId === apt.id}
                onClick={() => onCancel(apt.id)}
              >
                Cancel visit
              </Button>
            )}
          </Card>
        );
      })}
    </div>
  );
}
