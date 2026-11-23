import React from "react";
import { Card } from "@flatmate/ui";
import { formatIndianCompactCurrency } from "@/lib/utils";

interface Stat {
  label: string;
  value: React.ReactNode;
  hint: string;
  tone: string;
}

export function OwnerStats({ stats }: { stats: Stat[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4">
      {stats.map((s, i) => (
        <Card
          key={s.label}
          className={`p-4 border-slate-200/80 bg-white shadow-xs ${i === stats.length - 1 && stats.length % 2 ? "col-span-2 md:col-span-1" : ""}`}
        >
          <span className="text-[11px] font-semibold text-charcoal-muted uppercase block">{s.label}</span>
          <span className={`text-2xl font-black mt-1 block ${s.tone}`}>{s.value}</span>
          <span className="text-[10px] text-charcoal-muted mt-0.5 block">{s.hint}</span>
        </Card>
      ))}
    </div>
  );
}

export function buildOwnerStats(input: {
  totalProperties: number;
  activeListings: number;
  pendingApplications: number;
  visits: number;
  revenue: number;
}): Stat[] {
  return [
    { label: "Properties", value: input.totalProperties, hint: "Managed on Flatmate", tone: "text-charcoal" },
    { label: "Live listings", value: input.activeListings, hint: "Visible in search", tone: "text-forest" },
    { label: "Pending applications", value: input.pendingApplications, hint: "Waiting for your decision", tone: "text-amber-600" },
    { label: "Viewing requests", value: input.visits, hint: "Visits booked", tone: "text-blue-600" },
    { label: "Monthly revenue", value: formatIndianCompactCurrency(input.revenue), hint: "From current tenancies", tone: "text-charcoal" },
  ];
}
