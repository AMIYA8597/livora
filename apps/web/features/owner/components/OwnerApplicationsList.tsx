import React from "react";
import { Avatar, Badge, Button, Card } from "@flatmate/ui";
import { Check, X } from "lucide-react";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { OwnerApplication } from "../types";

const OPEN = new Set(["submitted", "reviewing", "pending"]);

interface OwnerApplicationsListProps {
  items: OwnerApplication[];
  busyId: string | null;
  onDecide: (id: string, status: "accepted" | "rejected") => void;
}

export function OwnerApplicationsList({ items, busyId, onDecide }: OwnerApplicationsListProps) {
  return (
    <div className="space-y-3">
      {items.map((app) => {
        const tone = app.status === "accepted" || app.status === "approved" ? "success" : app.status === "rejected" ? "danger" : "warning";
        return (
          <Card key={app.id} className="p-4 sm:p-5 border-slate-200/80 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-start gap-3 sm:gap-4 min-w-0">
              <Avatar alt={app.applicantName} size="md" />
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-bold text-charcoal text-sm">{app.applicantName}</h3>
                  <Badge variant={tone} className="capitalize">{app.status}</Badge>
                </div>
                <p className="text-xs text-charcoal mt-1 break-words">
                  Applying for <span className="font-semibold">{app.propertyTitle}</span>
                  {app.applicantOccupation && <span> • {app.applicantOccupation}</span>}
                </p>
                <p className="text-xs text-charcoal-muted mt-0.5">
                  Offers <span className="font-semibold text-charcoal">{formatCurrency(app.proposedRent, "INR")}</span> • Moving in{" "}
                  {formatDate(app.moveIn)}
                </p>
                {app.introduction && (
                  <p className="text-xs text-charcoal-muted mt-2 italic line-clamp-3 break-words">&ldquo;{app.introduction}&rdquo;</p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 md:shrink-0">
              {OPEN.has(app.status) ? (
                <>
                  <Button
                    size="sm"
                    variant="primary"
                    className="gap-1 flex-1 md:flex-none"
                    isLoading={busyId === app.id}
                    onClick={() => onDecide(app.id, "accepted")}
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>Accept</span>
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1 flex-1 md:flex-none text-rose-600 hover:bg-rose-50 border-rose-200"
                    disabled={busyId === app.id}
                    onClick={() => onDecide(app.id, "rejected")}
                  >
                    <X className="w-3.5 h-3.5" />
                    <span>Decline</span>
                  </Button>
                </>
              ) : (
                <span className="text-xs font-semibold text-charcoal-muted capitalize">Decision: {app.status}</span>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
