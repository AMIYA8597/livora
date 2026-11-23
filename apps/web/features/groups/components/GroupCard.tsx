import React from "react";
import type { GroupDTO } from "@flatmate/contracts";
import { Badge, Button, Card } from "@flatmate/ui";
import { Bookmark, Calendar, LogOut, MapPin, Sparkles, UserPlus } from "lucide-react";
import { formatCurrency, formatDate } from "@/lib/utils";

export function groupWishlist(group: GroupDTO) {
  return group.wishlist ?? group.wishlist_items ?? [];
}

interface GroupCardProps {
  group: GroupDTO;
  currentUserId?: string;
  busy: boolean;
  onJoin: () => void;
  onLeave: () => void;
  onOpenWishlist: () => void;
  onOpenCompatibility: () => void;
  onInvite: () => void;
}

export function GroupCard({ group, currentUserId, busy, onJoin, onLeave, onOpenWishlist, onOpenCompatibility, onInvite }: GroupCardProps) {
  const me = group.members.find((m) => m.user_id === currentUserId);
  const isCreator = group.creator_id === currentUserId;
  // The API lets only the creator or a leader add other people.
  const canInvite = isCreator || me?.role === "leader";

  return (
    <Card className="p-4 sm:p-6 border-warm-200 hover:shadow-md transition-shadow flex flex-col justify-between bg-white rounded-2xl">
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-bold text-charcoal text-lg break-words">{group.name}</h3>
            <div className="flex flex-wrap items-center text-xs text-charcoal-muted gap-x-2 gap-y-1 mt-1">
              <span className="flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-forest" />
                <span>{group.target_city}</span>
              </span>
              <span aria-hidden>•</span>
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-forest" />
                <span>Move-in {formatDate(group.target_move_in)}</span>
              </span>
            </div>
          </div>
          <Badge variant="brand" size="sm" className="shrink-0">
            {group.members.length} {group.members.length === 1 ? "member" : "members"}
          </Badge>
        </div>

        <p className="text-xs text-charcoal-muted mt-3 line-clamp-2 leading-relaxed break-words">
          {group.description || "Looking for compatible flatmates to rent a multi-bedroom place together."}
        </p>
      </div>

      <div className="mt-5 pt-4 border-t border-slate-100 space-y-3">
        <div>
          <span className="text-[11px] text-charcoal-muted uppercase font-semibold block">Combined budget</span>
          <span className="text-base font-bold text-charcoal">{formatCurrency(group.target_budget_total, "INR")}/mo</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" className="gap-1.5 border-warm-200 text-charcoal" onClick={onOpenWishlist}>
            <Bookmark className="w-3.5 h-3.5 text-forest" />
            <span>Wishlist ({groupWishlist(group).length})</span>
          </Button>
          <Button size="sm" variant="outline" className="gap-1.5 border-brand-200 text-forest" onClick={onOpenCompatibility}>
            <Sparkles className="w-3.5 h-3.5" />
            <span>Compatibility</span>
          </Button>
          {me ? (
            <>
              {canInvite && (
                <Button size="sm" variant="ghost" className="gap-1.5 text-forest" onClick={onInvite}>
                  <UserPlus className="w-4 h-4" />
                  <span>Invite</span>
                </Button>
              )}
              {!isCreator && (
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1 text-rose-600 border-rose-200 hover:bg-rose-50"
                  isLoading={busy}
                  onClick={onLeave}
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Leave</span>
                </Button>
              )}
            </>
          ) : (
            <Button size="sm" variant="secondary" isLoading={busy} onClick={onJoin}>
              Join group
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
