"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import type { PropertyDTO } from "@flatmate/contracts";
import { Button, ErrorState, ImageGallery, Skeleton } from "@flatmate/ui";
import { ArrowLeft, Flag, Heart } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { loginHref } from "@/lib/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useApiQuery } from "@/hooks/useApiQuery";
import { useSavedProperties } from "@/hooks/useSavedProperties";
import { ListingImage } from "@/components/ListingImage";
import { ReportModal } from "@/components/ReportModal";
import { InlineNotice } from "@/components/states/InlineNotice";
import { PropertyOverview } from "@/features/properties/components/PropertyOverview";
import { RoomsList } from "@/features/properties/components/RoomsList";
import { BookingCard } from "@/features/properties/components/BookingCard";
import { ApplyModal } from "@/features/properties/components/ApplyModal";
import { VisitModal } from "@/features/properties/components/VisitModal";

type ActiveModal =
  | { kind: "apply"; roomId: string | null; rent: number; nonce: number }
  | { kind: "visit"; nonce: number }
  | { kind: "report" }
  | null;

function DetailSkeleton() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-6" aria-busy="true">
      <Skeleton variant="text" width="120px" height="24px" />
      <Skeleton variant="rectangular" height="320px" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-4">
          <Skeleton variant="text" width="60%" height="36px" />
          <Skeleton variant="text" width="100%" height="80px" />
        </div>
        <Skeleton variant="card" height="320px" />
      </div>
    </div>
  );
}

/**
 * The listing view. The server page renders it with the listing already fetched (so the HTML
 * carries the content for search engines and a fast first paint); when the server couldn't see it
 * (e.g. the owner viewing their own unpublished listing), it's fetched here with the viewer's token.
 */
export function PropertyDetail({ initialProperty }: { initialProperty?: PropertyDTO | null }) {
  const params = useParams<{ id: string }>();
  const propertyId = params.id;
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const { isSaved, toggle } = useSavedProperties();

  const query = useApiQuery<PropertyDTO | null>(
    propertyId && !initialProperty ? `/properties/${propertyId}` : null,
    undefined,
    { allowNotFound: true },
  );
  const property = initialProperty ?? query.data;
  const { error, refetch } = query;
  const isLoading = !initialProperty && query.isLoading;

  const [modal, setModal] = useState<ActiveModal>(null);
  const [isStartingChat, setIsStartingChat] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  /** Sign-in comes before the form, not after the user has filled it in. */
  const requireAuth = (open: () => void) => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.push(loginHref(`/properties/${propertyId}`));
      return;
    }
    setActionError(null);
    open();
  };

  if (isLoading) return <DetailSkeleton />;

  if (error) {
    return (
      <div className="max-w-xl mx-auto px-4 py-20 text-center">
        <ErrorState title="Couldn't load this listing" message={error.message} onRetry={refetch} />
      </div>
    );
  }

  if (!property) {
    return (
      <div className="max-w-xl mx-auto px-4 py-20 text-center space-y-4">
        <h1 className="text-xl font-bold text-charcoal">Listing not found</h1>
        <p className="text-sm text-charcoal-muted">It may have been rented out or taken down by the owner.</p>
        <Link href="/properties">
          <Button variant="primary" className="min-h-[44px]">Browse listings</Button>
        </Link>
      </div>
    );
  }

  const currency = property.currency || "INR";
  const saved = isSaved(property.id);
  const isOwnListing = !!user && user.id === property.owner_id;

  const openApply = (roomId: string | null, rent: number) =>
    requireAuth(() => setModal({ kind: "apply", roomId, rent, nonce: Date.now() }));

  const messageHost = () =>
    requireAuth(async () => {
      setIsStartingChat(true);
      try {
        const res = await apiClient<{ conversation_id: string }>("/messaging/conversations", {
          method: "POST",
          body: JSON.stringify({
            participant_user_ids: [property.owner_id],
            type: "direct",
            property_id: property.id,
          }),
        });
        router.push(`/messages?conversationId=${encodeURIComponent(res.conversation_id)}`);
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Couldn't start a conversation with the host");
        setIsStartingChat(false);
      }
    });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6 sm:space-y-8">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => router.back()}
          className="inline-flex items-center min-h-[44px] text-xs font-semibold text-charcoal-muted hover:text-forest transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          <span>Back to listings</span>
        </button>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => toggle(property.id)}
            aria-pressed={saved}
            className={`inline-flex items-center gap-1.5 min-h-[44px] px-3 rounded-xl border text-xs font-semibold transition-all ${
              saved ? "bg-rose-50 border-rose-200 text-rose-600" : "bg-white border-warm-200 text-charcoal hover:bg-slate-50"
            }`}
          >
            <Heart className={`w-4 h-4 ${saved ? "fill-rose-500 text-rose-500" : ""}`} />
            <span>{saved ? "Saved" : "Save"}</span>
          </button>
          {!isOwnListing && (
            <button
              type="button"
              onClick={() => requireAuth(() => setModal({ kind: "report" }))}
              className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-charcoal-muted hover:text-rose-600 rounded-xl hover:bg-rose-50 transition-colors"
              aria-label="Report this listing"
              title="Report this listing"
            >
              <Flag className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {actionError && <InlineNotice tone="error">{actionError}</InlineNotice>}

      <ImageGallery
        images={property.images || []}
        alt={property.title}
        className="shadow-sm border border-warm-200"
        renderImage={({ src, alt, variant, index }) => (
          <ListingImage
            src={src}
            alt={alt}
            sizes={variant === "main" ? "(max-width: 1280px) 100vw, 1216px" : "80px"}
            priority={variant === "main" && index === 0}
            className="object-cover"
          />
        )}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8 min-w-0">
          <PropertyOverview property={property} />
          {!isOwnListing && (
            <RoomsList
              rooms={property.rooms ?? []}
              currency={currency}
              onApply={(room) => openApply(room.id, room.room_rent)}
            />
          )}
        </div>
        <div>
          <BookingCard
            property={property}
            isOwnListing={isOwnListing}
            isStartingChat={isStartingChat}
            onApply={() => openApply(null, property.monthly_rent)}
            onSchedule={() => requireAuth(() => setModal({ kind: "visit", nonce: Date.now() }))}
            onMessage={messageHost}
          />
        </div>
      </div>

      {modal?.kind === "apply" && (
        <ApplyModal
          key={modal.nonce}
          isOpen
          onClose={() => setModal(null)}
          propertyId={property.id}
          roomId={modal.roomId}
          defaultRent={modal.rent}
          currency={currency}
        />
      )}
      {modal?.kind === "visit" && (
        <VisitModal
          key={modal.nonce}
          isOpen
          onClose={() => setModal(null)}
          propertyId={property.id}
          hostId={property.owner_id}
          roomId={null}
        />
      )}
      {modal?.kind === "report" && (
        <ReportModal
          isOpen
          onClose={() => setModal(null)}
          targetType="property"
          targetId={property.id}
          targetName={property.title}
        />
      )}
    </div>
  );
}
