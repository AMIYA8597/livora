import React from "react";
import Link from "next/link";
import { Badge, Button, Card } from "@flatmate/ui";
import { Eye, MapPin, PauseCircle, PlayCircle, Star } from "lucide-react";
import { formatCurrency, placeLabel } from "@/lib/utils";
import type { OwnerProperty } from "../types";

interface OwnerPropertiesListProps {
  properties: OwnerProperty[];
  busyId: string | null;
  onToggleStatus: (property: OwnerProperty) => void;
  onVacateBed: (bedId: string) => void;
  /** Present when paid plans exist: feature or unfeature a published listing (Owner Pro). */
  onToggleFeatured?: (property: OwnerProperty) => void;
}

export function OwnerPropertiesList({ properties, busyId, onToggleStatus, onVacateBed, onToggleFeatured }: OwnerPropertiesListProps) {
  return (
    <div className="space-y-4">
      {properties.map((prop) => {
        const live = prop.listing_status === "published" || (!prop.listing_status && prop.is_active);
        return (
          <Card key={prop.id} className="p-4 sm:p-5 border-slate-200/80 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-bold text-charcoal text-base break-words">{prop.title}</h3>
                  <Badge variant={live ? "success" : "default"} className="capitalize">
                    {prop.listing_status || (live ? "published" : "paused")}
                  </Badge>
                  {prop.is_verified && <Badge variant="forest">Verified</Badge>}
                  {prop.is_featured && <Badge variant="warning">Featured</Badge>}
                </div>
                <p className="text-xs text-charcoal-muted mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
                  <MapPin className="w-3.5 h-3.5 shrink-0" />
                  <span>{placeLabel(prop.address_display, prop.city)}</span>
                  <span aria-hidden>•</span>
                  <span className="font-semibold text-charcoal">{formatCurrency(prop.monthly_rent, "INR")}/mo</span>
                  <span aria-hidden>•</span>
                  <span>Deposit {formatCurrency(prop.security_deposit, "INR")}</span>
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5"
                  isLoading={busyId === prop.id}
                  onClick={() => onToggleStatus(prop)}
                >
                  {live ? (
                    <>
                      <PauseCircle className="w-3.5 h-3.5 text-amber-600" />
                      <span>Pause listing</span>
                    </>
                  ) : (
                    <>
                      <PlayCircle className="w-3.5 h-3.5 text-forest" />
                      <span>Publish listing</span>
                    </>
                  )}
                </Button>
                {onToggleFeatured && live && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1.5"
                    isLoading={busyId === `feature-${prop.id}`}
                    onClick={() => onToggleFeatured(prop)}
                  >
                    <Star className={`w-3.5 h-3.5 ${prop.is_featured ? "fill-amber-400 text-amber-500" : "text-amber-500"}`} />
                    <span>{prop.is_featured ? "Unfeature" : "Feature"}</span>
                  </Button>
                )}
                <Link
                  href={`/properties/${prop.id}`}
                  className="inline-flex items-center gap-1 min-h-[36px] px-3 rounded-xl text-sm font-medium text-charcoal hover:bg-slate-100"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>View public page</span>
                </Link>
              </div>
            </div>

            {prop.rooms && prop.rooms.length > 0 && (
              <div className="pt-3 border-t border-slate-100 space-y-2">
                <span className="text-xs font-semibold text-charcoal block">Rooms and beds</span>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {prop.rooms.map((room) => (
                    <div key={room.id} className="p-3 bg-warm rounded-xl border border-slate-200/60 text-xs">
                      <div className="flex items-center justify-between gap-2 font-semibold text-charcoal">
                        <span className="truncate">{room.room_name}</span>
                        <span className="text-forest shrink-0">{formatCurrency(room.room_rent, "INR")}/mo</span>
                      </div>
                      <ul className="mt-2 space-y-1">
                        {room.beds?.map((bed) => (
                          <li key={bed.id} className="flex items-center justify-between gap-2 text-[11px] text-charcoal-muted">
                            <span className="truncate">{bed.bed_identifier}</span>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <Badge variant={bed.is_occupied ? "warning" : "success"} size="sm">
                                {bed.is_occupied ? "Occupied" : "Vacant"}
                              </Badge>
                              {bed.is_occupied && (
                                <button
                                  type="button"
                                  disabled={busyId === bed.id}
                                  onClick={() => onVacateBed(bed.id)}
                                  className="px-2 text-forest font-bold hover:underline disabled:opacity-50"
                                >
                                  Mark vacant
                                </button>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}
