import React from "react";
import { Trash2 } from "lucide-react";
import { FileUpload } from "@/components/FileUpload";
import { InlineNotice } from "@/components/states/InlineNotice";
import { formatCurrency } from "@/lib/utils";
import { displayTitle } from "../draft";
import type { StepProps } from "./fields";

export function PhotosStep({ draft, update }: StepProps) {
  return (
    <div className="space-y-4">
      <FileUpload
        bucket="properties"
        purpose="listing_gallery"
        label="Photos"
        helperText="Real photos of the bedrooms, living area and bathrooms. JPEG, PNG or WebP up to 10 MB."
        onUploadSuccess={(res) => update({ images: [...draft.images, res.url] })}
      />
      {draft.images.length > 0 && (
        <ul className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
          {draft.images.map((url, i) => (
            <li key={url} className="relative rounded-xl overflow-hidden h-28 border border-slate-200">
              <img src={url} alt={`Photo ${i + 1}`} className="w-full h-full object-cover" />
              <button
                type="button"
                aria-label={`Remove photo ${i + 1}`}
                onClick={() => update({ images: draft.images.filter((u) => u !== url) })}
                className="absolute top-1 right-1 inline-flex items-center justify-center min-w-[44px] min-h-[44px] text-white"
              >
                <span className="bg-black/60 rounded-full p-1.5">
                  <Trash2 className="w-3.5 h-3.5" />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ReviewStep({ draft }: StepProps) {
  const beds = draft.rooms.reduce((n, r) => n + r.beds.length, 0);
  return (
    <div className="space-y-4 text-xs text-charcoal">
      <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
        <h3 className="font-bold text-sm text-charcoal break-words">{displayTitle(draft)}</h3>
        <p className="text-charcoal-muted">
          {draft.locality}, {draft.city} {draft.postalCode}
        </p>
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          <div>
            <dt className="text-charcoal-muted">Rent</dt>
            <dd className="font-semibold">{formatCurrency(Number(draft.monthlyRent) || 0, "INR")}/mo</dd>
          </div>
          <div>
            <dt className="text-charcoal-muted">Deposit</dt>
            <dd className="font-semibold">{formatCurrency(Number(draft.deposit) || 0, "INR")}</dd>
          </div>
          <div>
            <dt className="text-charcoal-muted">Rooms / beds</dt>
            <dd className="font-semibold">
              {draft.rooms.length} / {beds}
            </dd>
          </div>
          <div>
            <dt className="text-charcoal-muted">Photos</dt>
            <dd className="font-semibold">{draft.images.length}</dd>
          </div>
        </dl>
      </div>
      {draft.images.length === 0 && (
        <InlineNotice tone="error">No photos yet. Listings without photos get far fewer applications.</InlineNotice>
      )}
      <p className="text-charcoal-muted text-[11px]">
        By publishing you confirm you own this place or are authorised to rent it out, under our terms of service.
      </p>
    </div>
  );
}
