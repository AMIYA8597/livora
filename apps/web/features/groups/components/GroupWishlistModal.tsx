"use client";

import React, { useState } from "react";
import type { GroupDTO, GroupWishlistItemDTO, PropertyDTO } from "@flatmate/contracts";
import { Button, Input, Modal } from "@flatmate/ui";
import { Bookmark } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useApiQuery } from "@/hooks/useApiQuery";
import { InlineNotice } from "@/components/states/InlineNotice";
import { extractPropertyId } from "@/lib/listing-link";
import { GroupWishlistCard } from "./GroupWishlistCard";
import { groupWishlist } from "./GroupCard";


/** One shortlisted flat, shown with its real title, area and rent. */
function WishlistEntry({
  item,
  currentUserId,
  isMember,
  onVote,
}: {
  item: GroupWishlistItemDTO;
  currentUserId: string;
  isMember: boolean;
  onVote: (propertyId: string, vote: "up" | "down" | "neutral") => Promise<void>;
}) {
  const { data: property, isLoading } = useApiQuery<PropertyDTO | null>(`/properties/${item.property_id}`, undefined, {
    allowNotFound: true,
  });
  if (isLoading) return <div className="h-24 rounded-2xl bg-slate-100 animate-pulse" aria-busy="true" />;
  return (
    <GroupWishlistCard
      propertyId={item.property_id}
      title={property ? property.title : "Listing no longer available"}
      locality={property ? property.address_display || property.city || "" : ""}
      monthlyRent={property?.monthly_rent ?? 0}
      votes={item.votes as Record<string, string>}
      currentUserId={currentUserId}
      isMember={isMember}
      onVote={onVote}
    />
  );
}

interface GroupWishlistModalProps {
  groupId: string;
  currentUserId: string;
  onClose: () => void;
  onChanged: () => void;
}

export function GroupWishlistModal({ groupId, currentUserId, onClose, onChanged }: GroupWishlistModalProps) {
  const { data: group, error, isLoading, refetch } = useApiQuery<GroupDTO>(`/groups/${groupId}`);
  const [link, setLink] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const isMember = !!group?.members.some((m) => m.user_id === currentUserId);
  const items = group ? groupWishlist(group) : [];

  const vote = async (propertyId: string, value: "up" | "down" | "neutral") => {
    await apiClient(`/groups/${groupId}/wishlist/${propertyId}/vote`, { method: "POST", body: JSON.stringify({ vote: value }) });
    refetch();
    onChanged();
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const propertyId = extractPropertyId(link);
    if (!propertyId) {
      setFormError("Paste a listing link (it contains /properties/…) or the listing ID.");
      return;
    }
    setIsAdding(true);
    setFormError(null);
    try {
      // An "up" vote on a property that isn't shortlisted yet adds it.
      await vote(propertyId, "up");
      setLink("");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Couldn't add that listing");
    } finally {
      setIsAdding(false);
    }
  };

  return (
    <Modal isOpen onClose={onClose} title={group ? `${group.name}: wishlist` : "Group wishlist"} description="Flats the group has shortlisted, with everyone's votes.">
      <div className="space-y-4 mt-2">
        {isMember && (
          <form onSubmit={handleAdd} className="space-y-2">
            {formError && <InlineNotice tone="error">{formError}</InlineNotice>}
            <div className="flex flex-col min-[400px]:flex-row gap-2">
              <Input
                aria-label="Listing link or ID"
                placeholder="Paste a listing link"
                value={link}
                onChange={(e) => setLink(e.target.value)}
                className="flex-1"
              />
              <Button type="submit" variant="primary" isLoading={isAdding} className="shrink-0">
                Add
              </Button>
            </div>
          </form>
        )}

        {isLoading ? (
          <div className="h-24 rounded-2xl bg-slate-100 animate-pulse" aria-busy="true" />
        ) : error ? (
          <div className="space-y-2">
            <InlineNotice tone="error">{error.message}</InlineNotice>
            <Button variant="outline" size="sm" onClick={refetch}>Try again</Button>
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-8">
            <Bookmark className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h3 className="font-bold text-charcoal text-sm">Nothing shortlisted yet</h3>
            <p className="text-xs text-charcoal-muted mt-1">
              {isMember ? "Paste a listing link above to add it for the group to vote on." : "Join the group to shortlist and vote."}
            </p>
          </div>
        ) : (
          <div className="space-y-3 max-h-[60dvh] overflow-y-auto">
            {items.map((item) => (
              <WishlistEntry key={item.id} item={item} currentUserId={currentUserId} isMember={isMember} onVote={vote} />
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}
