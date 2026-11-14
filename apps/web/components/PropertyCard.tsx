"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { PropertyDTO } from "@flatmate/contracts";
import { Card, Badge } from "@flatmate/ui";
import { formatCurrency, formatDate } from "@/lib/utils";
import { MapPin, Bed, Bath, Sparkles, Heart, ShieldCheck, Check } from "lucide-react";

export interface PropertyCardProps {
  property: PropertyDTO;
  matchScore?: number;
  onSaveToggle?: (propertyId: string, isSaved: boolean) => void;
}

export const PropertyCard: React.FC<PropertyCardProps> = ({
  property,
  matchScore,
  onSaveToggle,
}) => {
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = JSON.parse(localStorage.getItem("flatmate_saved_properties") || "[]");
        setIsSaved(saved.includes(property.id));
      } catch {
        setIsSaved(false);
      }
    }
  }, [property.id]);

  const toggleSave = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (typeof window === "undefined") return;

    try {
      const saved = JSON.parse(localStorage.getItem("flatmate_saved_properties") || "[]");
      let updated: string[];
      if (saved.includes(property.id)) {
        updated = saved.filter((id: string) => id !== property.id);
        setIsSaved(false);
      } else {
        updated = [...saved, property.id];
        setIsSaved(true);
      }
      localStorage.setItem("flatmate_saved_properties", JSON.stringify(updated));
      onSaveToggle?.(property.id, !isSaved);
    } catch {
      // Ignored
    }
  };

  const thumbnail =
    property.images && property.images.length > 0
      ? property.images[0]
      : "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600";

  const displayLocation =
    property.address_display || (property.city ? `${property.city}` : "India");

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
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={thumbnail}
            alt={property.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />

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
