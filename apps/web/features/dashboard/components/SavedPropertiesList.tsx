"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { PropertyDTO } from "@flatmate/contracts";
import { Badge, Button, Card, EmptyState } from "@flatmate/ui";
import { Heart, MapPin, Trash2 } from "lucide-react";
import { useApiQuery } from "@/hooks/useApiQuery";
import { useSavedProperties } from "@/hooks/useSavedProperties";
import { formatCurrency } from "@/lib/utils";

function SavedPropertyCard({ id, onRemove }: { id: string; onRemove: (id: string) => void }) {
  const query = useApiQuery<PropertyDTO | null>(`/properties/${id}`, undefined, { allowNotFound: true });
  const prop = query.data;

  if (query.isLoading) {
    return <div className="h-48 bg-slate-100 rounded-2xl animate-pulse" aria-busy="true" />;
  }
  if (query.error || !prop) {
    return (
      <Card className="p-5 border-dashed border-slate-300 flex flex-col justify-between gap-3">
        <p className="text-sm text-charcoal-muted">
          {query.error ? "Couldn't load this listing." : "This listing is no longer available."}
        </p>
        <div className="flex gap-2">
          {query.error && (
            <Button size="sm" variant="outline" className="min-h-[44px]" onClick={query.refetch}>Retry</Button>
          )}
          <Button size="sm" variant="ghost" className="min-h-[44px] text-rose-600" onClick={() => onRemove(id)}>
            Remove
          </Button>
        </div>
      </Card>
    );
  }
  return (
    <Card className="p-5 border-slate-200/80 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-2">
          <Badge variant="forest">{prop.configuration}</Badge>
          <button
            type="button"
            onClick={() => onRemove(prop.id)}
            aria-label={`Remove ${prop.title} from saved`}
            className="min-h-[44px] px-2 -mr-2 text-xs text-rose-500 hover:text-rose-700 flex items-center gap-1"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Remove</span>
          </button>
        </div>
        <h3 className="font-bold text-charcoal text-base mb-1 break-words">{prop.title}</h3>
        <p className="text-xs text-charcoal-muted flex items-center gap-1 mb-3">
          <MapPin className="w-3.5 h-3.5 text-forest shrink-0" />
          <span className="truncate">{[prop.address_display, prop.city].filter(Boolean).join(", ")}</span>
        </p>
        <div className="text-lg font-bold text-charcoal">
          {formatCurrency(prop.monthly_rent, "INR")}
          <span className="text-xs font-normal text-charcoal-muted">/mo</span>
        </div>
      </div>
      <div className="pt-4 border-t border-slate-100 flex items-center justify-between gap-2 mt-3">
        <span className="text-xs text-charcoal-muted">Deposit: {formatCurrency(prop.security_deposit, "INR")}</span>
        <Link href={`/properties/${prop.id}`}>
          <Button size="sm" variant="primary" className="min-h-[44px]">View details</Button>
        </Link>
      </div>
    </Card>
  );
}

/** Properties hearted on any card; the list lives in localStorage (see lib/saved-properties.ts). */
export function SavedPropertiesList({ onRemoved }: { onRemoved?: () => void }) {
  const router = useRouter();
  const saved = useSavedProperties();
  const remove = (id: string) => {
    saved.remove(id);
    onRemoved?.();
  };

  if (saved.ids.length === 0) {
    return (
      <EmptyState
        icon={Heart}
        title="No saved properties yet"
        description="Tap the heart on any listing to keep it here for later."
        actionLabel="Browse properties"
        onAction={() => router.push("/properties")}
      />
    );
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {saved.ids.map((id) => (
        <SavedPropertyCard key={id} id={id} onRemove={remove} />
      ))}
    </div>
  );
}
