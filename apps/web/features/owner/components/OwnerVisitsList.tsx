import React from "react";
import { Badge, Button, Card } from "@flatmate/ui";
import { Calendar, Check, X } from "lucide-react";
import { formatDateTimeIST } from "@/lib/utils";
import type { OwnerAppointment } from "../types";

interface OwnerVisitsListProps {
  items: OwnerAppointment[];
  busyId: string | null;
  onDecide: (id: string, status: "confirmed" | "cancelled") => void;
}

export function OwnerVisitsList({ items, busyId, onDecide }: OwnerVisitsListProps) {
  return (
    <div className="space-y-3">
      {items.map((appt) => (
        <Card key={appt.id} className="p-4 border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-bold text-charcoal text-sm">Viewing request</span>
              <Badge
                variant={appt.status === "confirmed" ? "success" : appt.status === "cancelled" ? "danger" : "warning"}
                className="capitalize"
              >
                {appt.status}
              </Badge>
            </div>
            <p className="text-xs text-charcoal-muted mt-1 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-forest shrink-0" />
              <span>{formatDateTimeIST(appt.scheduled_at)}</span>
            </p>
            {appt.notes && <p className="text-xs text-charcoal-muted mt-1 italic break-words">&ldquo;{appt.notes}&rdquo;</p>}
          </div>

          {appt.status === "pending" && (
            <div className="flex items-center gap-2 sm:shrink-0">
              <Button
                size="sm"
                variant="primary"
                className="gap-1 flex-1 sm:flex-none"
                isLoading={busyId === appt.id}
                onClick={() => onDecide(appt.id, "confirmed")}
              >
                <Check className="w-3.5 h-3.5" />
                <span>Confirm</span>
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="gap-1 flex-1 sm:flex-none text-rose-600 border-rose-200"
                disabled={busyId === appt.id}
                onClick={() => onDecide(appt.id, "cancelled")}
              >
                <X className="w-3.5 h-3.5" />
                <span>Decline</span>
              </Button>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}
