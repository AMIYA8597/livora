"use client";

import React from "react";
import Link from "next/link";
import { PropertyDTO } from "@flatmate/contracts";
import { Card, Badge } from "@flatmate/ui";
import { formatCurrency, formatDate } from "@/lib/utils";
import { MapPin, Bed, Bath, Sparkles } from "lucide-react";

export interface PropertyCardProps {
  property: PropertyDTO;
  matchScore?: number;
}

export const PropertyCard: React.FC<PropertyCardProps> = ({ property, matchScore }) => {
  const thumbnail = property.images && property.images.length > 0
    ? property.images[0]
    : "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600";

  return (
    <Link href={`/properties/${property.id}`} className="group block h-full">
      <Card hoverable className="h-full flex flex-col border border-slate-200/80 shadow-2xs">
        {/* Image Container */}
        <div className="relative aspect-16/10 w-full overflow-hidden bg-slate-100">
          <img
            src={thumbnail}
            alt={property.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
          {/* Price Badge */}
          <div className="absolute bottom-3 left-3 bg-slate-900/85 backdrop-blur-md px-3 py-1.5 rounded-xl text-white font-semibold text-sm shadow-md">
            {formatCurrency(property.monthly_rent)}
            <span className="text-xs font-normal text-slate-300">/mo</span>
          </div>
          {/* Compatibility Badge if provided */}
          {matchScore !== undefined && (
            <div className="absolute top-3 right-3 bg-emerald-600 text-white font-bold text-xs px-2.5 py-1 rounded-full shadow-md flex items-center space-x-1">
              <Sparkles className="w-3 h-3" />
              <span>{Math.round(matchScore)}% Match</span>
            </div>
          )}
        </div>

        {/* Card Body */}
        <div className="p-4 flex-1 flex flex-col justify-between">
          <div>
            <div className="flex items-center text-xs text-slate-500 mb-1 space-x-1">
              <MapPin className="w-3.5 h-3.5 text-slate-400" />
              <span className="truncate">{property.address}, {property.city}</span>
            </div>
            <h3 className="font-semibold text-slate-900 text-base line-clamp-1 group-hover:text-indigo-600 transition-colors">
              {property.title}
            </h3>
            <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
              {property.description}
            </p>
          </div>

          {/* Amenities & specs */}
          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <div className="flex items-center space-x-3">
              <span className="flex items-center space-x-1">
                <Bed className="w-3.5 h-3.5 text-slate-400" />
                <span>{property.total_bedrooms} Beds</span>
              </span>
              <span className="flex items-center space-x-1">
                <Bath className="w-3.5 h-3.5 text-slate-400" />
                <span>{property.total_bathrooms} Baths</span>
              </span>
            </div>
            <span className="text-indigo-600 font-medium">Avail {formatDate(property.available_from)}</span>
          </div>
        </div>
      </Card>
    </Link>
  );
};
