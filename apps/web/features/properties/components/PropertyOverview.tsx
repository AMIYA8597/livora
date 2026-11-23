import React from "react";
import type { PropertyDTO } from "@flatmate/contracts";
import { Badge } from "@flatmate/ui";
import { Bath, Bed, Calendar, CheckCircle2, Info, MapPin, ShieldCheck } from "lucide-react";
import { formatCurrency, formatDate } from "@/lib/utils";

/** Title, location, specs, description, lease terms and amenities of a listing. */
export function PropertyOverview({ property }: { property: PropertyDTO }) {
  const currency = property.currency || "INR";
  const displayAddress = property.address_display || property.city || "India";
  const facts: { label: string; value: string }[] = [
    { label: "Monthly rent", value: formatCurrency(property.monthly_rent, currency) },
    { label: "Security deposit", value: formatCurrency(property.security_deposit ?? 0, currency) },
    { label: "Utilities & bills", value: property.bills_included ? "Included in rent" : "Billed separately" },
    { label: "Furnishing", value: property.furnishing_status?.replace(/_/g, " ") || "Not specified" },
    { label: "Pets", value: property.pets_allowed ? "Allowed" : "Not allowed" },
    { label: "Smoking", value: property.smoking_allowed ? "Allowed" : "Not allowed" },
  ];

  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
          <div className="flex items-center gap-1.5 text-xs text-charcoal-muted min-w-0">
            <MapPin className="w-4 h-4 text-forest shrink-0" />
            <span className="truncate">
              {displayAddress}
              {property.postal_code ? ` • ${property.postal_code}` : ""}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            {property.is_verified && (
              <Badge variant="forest" size="sm" className="gap-1">
                <ShieldCheck className="w-3.5 h-3.5" /> Verified listing
              </Badge>
            )}
            {property.property_category && (
              <Badge variant="warm" size="sm" className="capitalize">
                {property.property_category.replace(/_/g, " ")}
              </Badge>
            )}
          </div>
        </div>

        <h1 className="text-2xl sm:text-3xl font-extrabold text-charcoal tracking-tight break-words">{property.title}</h1>

        <div className="mt-3 text-xs bg-warm-50 p-3 rounded-xl border border-warm-200 flex items-start gap-2">
          <Info className="w-4 h-4 text-forest shrink-0 mt-0.5" />
          <p className="text-charcoal-muted leading-relaxed">
            <strong className="text-charcoal font-semibold">Exact address: </strong>
            {property.address_exact || "Shared once a viewing visit is confirmed."}
          </p>
        </div>

        <div className="flex flex-wrap gap-4 mt-5 pt-4 border-t border-slate-100 text-sm text-charcoal">
          <span className="flex items-center gap-1.5">
            <Bed className="w-4 h-4 text-forest" />
            <span className="font-semibold">{property.total_bedrooms} {property.total_bedrooms === 1 ? "bedroom" : "bedrooms"}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <Bath className="w-4 h-4 text-forest" />
            <span className="font-semibold">{property.total_bathrooms} {property.total_bathrooms === 1 ? "bathroom" : "bathrooms"}</span>
          </span>
          {property.available_from && (
            <span className="flex items-center gap-1.5">
              <Calendar className="w-4 h-4 text-forest" />
              <span>Available from {formatDate(property.available_from)}</span>
            </span>
          )}
        </div>
      </div>

      {property.description && (
        <section>
          <h2 className="text-lg font-bold text-charcoal mb-2">About the property</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed whitespace-pre-line break-words">{property.description}</p>
        </section>
      )}

      <section className="p-5 bg-warm-50/60 rounded-2xl border border-warm-200 space-y-3">
        <h2 className="text-sm font-bold text-charcoal uppercase tracking-wider">Lease details</h2>
        <dl className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
          {facts.map((f) => (
            <div key={f.label}>
              <dt className="text-charcoal-muted">{f.label}</dt>
              <dd className="font-bold text-charcoal text-sm capitalize">{f.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      {property.amenities && property.amenities.length > 0 && (
        <section>
          <h2 className="text-lg font-bold text-charcoal mb-3">Amenities</h2>
          <ul className="grid grid-cols-1 min-[400px]:grid-cols-2 sm:grid-cols-3 gap-2.5">
            {property.amenities.map((amenity) => (
              <li key={amenity} className="flex items-center gap-2 text-xs font-medium text-charcoal bg-warm-50 px-3.5 py-2.5 rounded-xl border border-warm-200">
                <CheckCircle2 className="w-4 h-4 text-forest shrink-0" />
                <span className="capitalize">{amenity.replace(/_/g, " ")}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
