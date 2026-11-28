"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ApplicationDTO } from "@flatmate/contracts";
import { Badge, Button, Card, EmptyState } from "@flatmate/ui";
import { FileText } from "lucide-react";
import { formatCurrency, formatDate } from "@/lib/utils";
import { ApplicationTimeline } from "@/features/applications/ApplicationTimeline";

const WITHDRAWABLE = new Set(["submitted", "reviewing", "under_review"]);

function statusVariant(status: string): "success" | "danger" | "warning" {
  if (status === "accepted" || status === "approved") return "success";
  if (status === "rejected" || status === "withdrawn") return "danger";
  return "warning";
}

interface ApplicationsListProps {
  items: ApplicationDTO[];
  onWithdraw: (applicationId: string) => void;
  busyId?: string | null;
}

export function ApplicationsList({ items, onWithdraw, busyId }: ApplicationsListProps) {
  const router = useRouter();
  if (items.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title="No applications yet"
        description="Find a flat or room you like and send the landlord or flatmates an introduction."
        actionLabel="Browse properties"
        onAction={() => router.push("/properties")}
      />
    );
  }
  return (
    <div className="space-y-4">
      {items.map((app) => (
        <Card key={app.id} className="p-5 border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 min-w-0">
              <Link
                href={`/properties/${app.property_id}`}
                className="font-semibold text-charcoal text-base truncate hover:underline"
              >
                {app.property_title || "Listing no longer available"}
              </Link>
              <Badge variant={statusVariant(app.status)} size="sm" className="capitalize shrink-0">
                {app.status.replace(/_/g, " ")}
              </Badge>
            </div>
            {app.property_city && <p className="text-xs text-charcoal-muted mt-0.5">{app.property_city}</p>}
            <p className="text-sm text-charcoal mt-1">
              Offered rent: {formatCurrency(app.proposed_rent, "INR")}/mo
            </p>
            <p className="text-xs text-charcoal-muted mt-1">
              Move-in: {formatDate(app.move_in_target)} • Sent: {formatDate(app.submitted_at)}
            </p>
            {app.introduction && (
              <p className="text-xs text-charcoal mt-2 italic bg-warm p-2.5 rounded-lg border border-slate-100 break-words">
                &ldquo;{app.introduction}&rdquo;
              </p>
            )}
            <ApplicationTimeline applicationId={app.id} viewer="applicant" />
          </div>

          <div className="flex items-center gap-2 self-stretch sm:self-center justify-end">
            {WITHDRAWABLE.has(app.status) && (
              <Button
                size="sm"
                variant="outline"
                className="min-h-[44px] text-rose-600 border-rose-200 hover:bg-rose-50"
                isLoading={busyId === app.id}
                onClick={() => onWithdraw(app.id)}
              >
                Withdraw
              </Button>
            )}
            <Link href={`/properties/${app.property_id}`}>
              <Button size="sm" variant="ghost" className="min-h-[44px]">View listing</Button>
            </Link>
          </div>
        </Card>
      ))}
    </div>
  );
}
