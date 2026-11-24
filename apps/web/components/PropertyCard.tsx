"use client";

import React from "react";
import { useSavedProperties } from "@/hooks/useSavedProperties";
import Link from "next/link";
import { PropertyDTO } from "@flatmate/contracts";
import { Card, Badge } from "@flatmate/ui";
import { formatCurrency, formatDate } from "@/lib/utils";
import { ListingImage } from "@/components/ListingImage";
import { MapPin, Bed, Bath, Sparkles, Heart, ShieldCheck, Check, ImageOff, Star } from "lucide-react";
import { formatDistance } from "@/lib/near-me";

export interface PropertyCardProps {
  property: PropertyDTO;
  matchScore?: number;
  onSaveToggle?: (propertyId: string, isSaved: boolean) => void;
  /** Set on the first cards of a grid so the largest image above the fold loads first. */
  priority?: boolean;
}

export const PropertyCard: React.FC<PropertyCardProps> = ({
  property,
  matchScore,
  onSaveToggle,
  priority = false,
}) => {
  const saved = useSavedProperties();
  const isSaved = saved.isSaved(property.id);

  const toggleSave = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Toggle first: `onSaveToggle?.(id, saved.toggle(id))` would skip the toggle when no
    // callback is passed (an optional call does not evaluate its arguments).
    const nowSaved = saved.toggle(property.id);
    onSaveToggle?.(property.id, nowSaved);
  };

  const thumbnail = property.images?.[0];

  const baseLocation = property.address_display || (property.city ? `${property.city}` : "India");
  const distance = formatDistance(property.distance_km);
  const displayLocation = distance ? `${baseLocation} · ${distance}` : baseLocation;

  const furnishingLabel =
    property.furnishing_status === "fully_furnished" || (property.furnishing_status as string) === "furnished"
      ? "Furnished"
      : property.furnishing_status === "semi_furnished"
      ? "Semi-Furnished"
      : "Unfurnished";

  return (
    <Link href={`/properties/${property.id}`} className="group block h-full">
      <Card hoverable className="h-full flex flex-col border border-warm-200 shadow-xs rounded-2xl overflow-hidden bg-white">
        {/* Image Container */}
        <div className="relative aspect-[16/10] w-full overflow-hidden bg-slate-100">
          {thumbnail ? (
            <ListingImage
              src={thumbnail}
              alt={property.title}
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
              priority={priority}
              className="object-cover group-hover:scale-105 transition-transform duration-300"
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-slate-400">
              <ImageOff className="w-8 h-8 mb-1" aria-hidden />
              <span className="text-xs font-medium">No photos yet</span>
            </div>
          )}

          {/* Save / Favorite Button */}
          <button
            onClick={toggleSave}
            type="button"
            aria-label={isSaved ? "Remove from saved" : "Save property"}
            className="absolute top-3 left-3 p-2 rounded-full bg-white/80 hover:bg-white text-charcoal shadow-md backdrop-blur-sm transition-all focus:outline-none"
          >
            <Heart
              className={`w-4 h-4 transition-colors ${
                isSaved ? "fill-rose-500 text-rose-500" : "text-charcoal-muted hover:text-rose-500"
              }`}
            />
          </button>

          {/* Badges on Top Right */}
          <div className="absolute top-3 right-3 flex flex-col items-end gap-1.5">
            {property.is_featured && (
              <span className="inline-flex items-center space-x-1 bg-amber-500/95 text-white text-[11px] font-bold px-2.5 py-1 rounded-full shadow-md">
                <Star className="w-3.5 h-3.5 fill-white" aria-hidden="true" />
                <span>Featured</span>
              </span>
            )}
            {property.is_verified && (
              <span className="inline-flex items-center space-x-1 bg-forest/90 text-white text-[11px] font-bold px-2.5 py-1 rounded-full shadow-md backdrop-blur-sm">
                <ShieldCheck className="w-3.5 h-3.5 text-pale-green" />
                <span>Verified</span>
              </span>
            )}

            {matchScore !== undefined && (
              <span className="inline-flex items-center space-x-1 bg-emerald-600 text-white font-bold text-xs px-2.5 py-1 rounded-full shadow-md">
                <Sparkles className="w-3 h-3" />
                <span>{Math.round(matchScore)}% Match</span>
              </span>
            )}
          </div>

          {/* Price & Deposit Overlay */}
          <div className="absolute bottom-3 left-3 bg-charcoal/85 backdrop-blur-md px-3 py-1.5 rounded-xl text-white font-semibold text-sm shadow-md">
            <span>{formatCurrency(property.monthly_rent, property.currency || "INR")}</span>
            <span className="text-[11px] font-normal text-warm-200"> /mo</span>
            {property.security_deposit && (
              <span className="text-[10px] text-warm-300 ml-1.5 font-normal border-l border-white/20 pl-1.5 hidden sm:inline">
                Dep: {formatCurrency(property.security_deposit)}
              </span>
            )}
          </div>
        </div>

        {/* Card Body */}
        <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
          <div>
            {property.match_reasons && property.match_reasons.length > 0 && (
              <ul className="flex flex-wrap gap-1 mb-1.5" aria-label="Why this is recommended">
                {property.match_reasons.slice(0, 2).map((reason) => (
                  <li key={reason} className="text-[10px] font-semibold text-forest bg-pale-green/40 border border-brand-200 px-1.5 py-0.5 rounded-md">
                    {reason}
                  </li>
                ))}
              </ul>
            )}
            <div className="flex items-center justify-between text-xs text-charcoal-muted mb-1">
              <div className="flex items-center space-x-1 truncate max-w-[70%]">
                <MapPin className="w-3.5 h-3.5 text-forest shrink-0" />
                <span className="truncate">{displayLocation}</span>
              </div>
              <span className="text-[11px] font-semibold text-forest bg-pale-green/40 px-2 py-0.5 rounded-md">
                {furnishingLabel}
              </span>
            </div>

            <h3 className="font-bold text-charcoal text-base line-clamp-1 group-hover:text-forest transition-colors">
              {property.title}
            </h3>

            <p className="text-xs text-charcoal-muted mt-1 line-clamp-2 leading-relaxed">
              {property.description}
            </p>
          </div>

          {/* Amenities & specs */}
          <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-charcoal">
            <div className="flex items-center space-x-3">
              <span className="flex items-center space-x-1">
                <Bed className="w-3.5 h-3.5 text-forest" />
                <span>{property.total_bedrooms} Beds</span>
              </span>
              <span className="flex items-center space-x-1">
                <Bath className="w-3.5 h-3.5 text-forest" />
                <span>{property.total_bathrooms} Baths</span>
              </span>
            </div>
            <span className="text-secondary-green font-medium">
              From {formatDate(property.available_from)}
            </span>
          </div>
        </div>
      </Card>
    </Link>
  );
};
