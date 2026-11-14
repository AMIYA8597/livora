"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { GroupDTO, GroupCompatibilityResponse } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";
import { Card, Button, Modal, Input, Badge, Skeleton, EmptyState, ErrorState } from "@flatmate/ui";
import { GroupWishlistCard } from "@/features/groups/components/GroupWishlistCard";
import {
  Users,
  Plus,
  MapPin,
  Calendar,
  Sparkles,
  CheckCircle2,
  ShieldAlert,
  LogOut,
  Heart,
  Bookmark,
  UserPlus,
  Send,
} from "lucide-react";

export default function GroupsPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuth();
  const [groups, setGroups] = useState<GroupDTO[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create Group Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [city, setCity] = useState("Bengaluru");
  const [budget, setBudget] = useState("50000");
  const [moveIn, setMoveIn] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Group Compatibility Modal
  const [compatibilityModalOpen, setCompatibilityModalOpen] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<GroupDTO | null>(null);
  const [compatibilityData, setCompatibilityData] = useState<GroupCompatibilityResponse | null>(null);
  const [loadingCompatibility, setLoadingCompatibility] = useState(false);

  // Wishlist Modal
  const [wishlistModalOpen, setWishlistModalOpen] = useState(false);
  const [wishlistGroup, setWishlistGroup] = useState<GroupDTO | null>(null);
  const [newPropertyId, setNewPropertyId] = useState("");
  const [isAddingProperty, setIsAddingProperty] = useState(false);

  // Invite Modal
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [inviteTargetGroupId, setInviteTargetGroupId] = useState<string>("");
  const [inviteUserId, setInviteUserId] = useState("");
  const [isInviting, setIsInviting] = useState(false);
  const [inviteMessage, setInviteMessage] = useState<string | null>(null);

  const fetchGroups = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiClient<GroupDTO[]>("/groups/");
      setGroups(data || []);
    } catch (err: any) {
      console.error("Failed to load groups:", err);
      setError(err.message || "Failed to load hunting groups");
      setGroups([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGroups();
  }, []);

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    try {
      setIsSubmitting(true);
      await apiClient("/groups/", {
        method: "POST",
        body: JSON.stringify({
          name,
          description,
          target_city: city,
          target_budget_total: parseInt(budget, 10),
          target_move_in: moveIn || undefined,
        }),
      });
      setIsModalOpen(false);
      setName("");
      setDescription("");
      fetchGroups();
    } catch (err: any) {
      alert(err.message || "Failed to create group");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleJoinGroup = async (groupId: string) => {
    if (!isAuthenticated || !user) {
      router.push("/login");
      return;
    }
    try {
      await apiClient(`/groups/${groupId}/members`, {
        method: "POST",
        body: JSON.stringify({
          user_id: user.id,
          role: "member",
        }),
      });
      alert("You have joined this hunting syndicate!");
      fetchGroups();
    } catch (err: any) {
      alert(err.message || "Failed to join group");
    }
  };

  const handleLeaveGroup = async (groupId: string) => {
    if (!user) return;
    try {
      await apiClient(`/groups/${groupId}/members/${user.id}`, { method: "DELETE" });
      fetchGroups();
    } catch (err: any) {
      alert(err.message || "Failed to leave group");
    }
  };

  const handleViewCompatibility = async (group: GroupDTO) => {
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    try {
      setSelectedGroup(group);
      setLoadingCompatibility(true);
      setCompatibilityModalOpen(true);
      const data = await apiClient<GroupCompatibilityResponse>(`/groups/${group.id}/compatibility`);
      setCompatibilityData(data);
    } catch (err: any) {
      alert(err.message || "Failed to calculate group compatibility");
    } finally {
      setLoadingCompatibility(false);
    }
  };

  const handleOpenWishlist = (group: GroupDTO) => {
    setWishlistGroup(group);
    setWishlistModalOpen(true);
  };

  const handleVoteWishlist = async (propertyId: string, vote: "up" | "down" | "neutral") => {
    if (!wishlistGroup || !user) return;
    try {
      await apiClient(`/groups/${wishlistGroup.id}/wishlist/${propertyId}/vote`, {
        method: "POST",
        body: JSON.stringify({ vote }),
      });
      const freshGroup = await apiClient<GroupDTO>(`/groups/${wishlistGroup.id}`);
      setWishlistGroup(freshGroup);
      fetchGroups();
    } catch (err: any) {
      alert(err.message || "Failed to submit vote");
    }
  };

  const handleAddPropertyToWishlist = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!wishlistGroup || !newPropertyId.trim()) return;

    try {
      setIsAddingProperty(true);
      // Voting "up" on a property in group wishlist automatically adds it
      await apiClient(`/groups/${wishlistGroup.id}/wishlist/${newPropertyId.trim()}/vote`, {
        method: "POST",
        body: JSON.stringify({ vote: "up" }),
      });
      const freshGroup = await apiClient<GroupDTO>(`/groups/${wishlistGroup.id}`);
      setWishlistGroup(freshGroup);
      setNewPropertyId("");
      fetchGroups();
    } catch (err: any) {
      alert(err.message || "Failed to add property to wishlist");
    } finally {
      setIsAddingProperty(false);
    }
  };

  const handleSendMemberInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteTargetGroupId || !inviteUserId.trim()) return;

    try {
      setIsInviting(true);
      setInviteMessage(null);
      await apiClient(`/groups/${inviteTargetGroupId}/members`, {
        method: "POST",
        body: JSON.stringify({
          user_id: inviteUserId.trim(),
          role: "member",
        }),
      });
      setInviteMessage("Member invited and added to syndicate roster!");
      setInviteUserId("");
      fetchGroups();
      setTimeout(() => {
        setInviteModalOpen(false);
        setInviteMessage(null);
      }, 2000);
    } catch (err: any) {
      alert(err.message || "Failed to send member invitation");
    } finally {
      setIsInviting(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-1.5 bg-pale-green/40 text-forest text-xs font-semibold px-3 py-1 rounded-full mb-2 border border-brand-200">
            <Users className="w-3.5 h-3.5 text-secondary-green" />
            <span>Team-Up to Rent</span>
          </div>
          <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">
            Flatmate Hunting Groups & Syndicates
          </h1>
          <p className="text-charcoal-muted text-sm mt-1">
            Form syndicates with compatible seekers to search, pool budgets, vote on wishlists, and apply together.
          </p>
        </div>

        {isAuthenticated && (
          <Button variant="primary" className="gap-2" onClick={() => setIsModalOpen(true)}>
            <Plus className="w-4 h-4" />
            <span>Start a Group</span>
          </Button>
        )}
      </div>

      {error && (
        <ErrorState
          title="Could not load groups"
          message={error}
          onRetry={fetchGroups}
        />
      )}

      {/* Groups Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[1, 2, 3, 4].map((n) => (
            <Skeleton key={n} variant="card" height={220} />
          ))}
        </div>
      ) : groups.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No active hunting syndicates found"
          description="Create a team-up group to pool budgets and hunt for apartments with compatible flatmates."
          actionLabel={isAuthenticated ? "Start a Group" : "Sign In to Start"}
          onAction={() => (isAuthenticated ? setIsModalOpen(true) : router.push("/login"))}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {groups.map((group) => {
            const isMember = group.members.some((m) => m.user_id === user?.id);
            const isCreator = group.creator_id === user?.id;

            return (
              <Card
                key={group.id}
                className="p-6 border-warm-200 hover:shadow-md transition-shadow flex flex-col justify-between bg-white rounded-2xl"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-bold text-charcoal text-lg">{group.name}</h3>
                      <div className="flex items-center text-xs text-charcoal-muted space-x-2 mt-1">
                        <span className="flex items-center space-x-1">
                          <MapPin className="w-3.5 h-3.5 text-forest" />
                          <span>{group.target_city}</span>
                        </span>
                        <span>•</span>
                        <span className="flex items-center space-x-1">
                          <Calendar className="w-3.5 h-3.5 text-forest" />
                          <span>Move-in: {formatDate(group.target_move_in)}</span>
                        </span>
                      </div>
                    </div>
                    <Badge variant="brand" size="sm">
                      {group.members.length} Members
                    </Badge>
                  </div>

                  <p className="text-xs text-charcoal-muted mt-3 line-clamp-2 leading-relaxed">
                    {group.description || "Looking for compatible flatmates to rent a multi-bedroom place together."}
                  </p>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <span className="text-[11px] text-charcoal-muted uppercase font-semibold block">
                      Combined Target Budget
                    </span>
                    <span className="text-base font-bold text-charcoal">
                      {formatCurrency(group.target_budget_total, "INR")}/mo
                    </span>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1.5 border-warm-200 text-charcoal"
                      onClick={() => handleOpenWishlist(group)}
                    >
                      <Bookmark className="w-3.5 h-3.5 text-forest" />
                      <span>Wishlist ({group.wishlist?.length || 0})</span>
                    </Button>

                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1.5 border-brand-200 text-forest hover:bg-pale-green/20"
                      onClick={() => handleViewCompatibility(group)}
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Compatibility</span>
                    </Button>

                    {isMember ? (
                      <div className="flex items-center space-x-1.5">
                        <Button
                          size="sm"
                          variant="ghost"
                          title="Invite Member"
                          onClick={() => {
                            setInviteTargetGroupId(group.id);
                            setInviteModalOpen(true);
                          }}
                        >
                          <UserPlus className="w-4 h-4 text-forest" />
                        </Button>
                        {!isCreator && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-rose-600 border-rose-200 hover:bg-rose-50"
                            onClick={() => handleLeaveGroup(group.id)}
                          >
                            <LogOut className="w-3.5 h-3.5 mr-1" />
                            Leave
                          </Button>
                        )}
                      </div>
                    ) : (
                      <Button size="sm" variant="secondary" onClick={() => handleJoinGroup(group.id)}>
                        Join Syndicate
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create Group Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Start a Flatmate Syndicate"
        description="Create a team-up group to invite seekers, pool budget, and vote on properties."
      >
        <form onSubmit={handleCreateGroup} className="space-y-4 mt-2">
          <Input
            label="Group Name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Koramangala / HSR Tech Flatshare"
          />

          <div>
            <label className="block text-xs font-semibold text-charcoal mb-1">Description & Goals</label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What kind of apartment are you aiming for? Any quiet hour or lifestyle expectations?"
              className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Target City"
              required
              value={city}
              onChange={(e) => setCity(e.target.value)}
            />
            <Input
              label="Combined Target Budget (₹)"
              type="number"
              required
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
          </div>

          <Input
            label="Target Move-In Date"
            type="date"
            value={moveIn}
            onChange={(e) => setMoveIn(e.target.value)}
          />

          <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSubmitting}>
            Launch Syndicate
          </Button>
        </form>
      </Modal>

      {/* Group Compatibility Modal */}
      <Modal
        isOpen={compatibilityModalOpen}
        onClose={() => setCompatibilityModalOpen(false)}
        title={selectedGroup ? `${selectedGroup.name} — Compatibility` : "Group Compatibility"}
        description="Collective cohesion score computed across all member pairs."
      >
        {loadingCompatibility ? (
          <div className="py-8 text-center text-xs text-charcoal-muted">
            Calculating pairwise member vectors...
          </div>
        ) : compatibilityData ? (
          <div className="space-y-5 mt-2">
            <div className="flex items-center justify-between p-4 bg-pale-green/30 rounded-2xl border border-brand-200">
              <div>
                <span className="text-xs font-bold text-forest uppercase tracking-wider block">
                  Collective Synergy
                </span>
                <span className="text-2xl font-extrabold text-forest">
                  {Math.round(compatibilityData.collective_score)}%
                </span>
              </div>
              <Badge variant={compatibilityData.dealbreakers_cleared ? "success" : "danger"}>
                {compatibilityData.dealbreakers_cleared ? "Dealbreakers Cleared" : "Dealbreaker Flagged"}
              </Badge>
            </div>

            {compatibilityData.pairwise_breakdowns && compatibilityData.pairwise_breakdowns.length > 0 && (
              <div>
                <h4 className="text-xs font-bold text-charcoal uppercase mb-2">Member Pair Breakdowns</h4>
                <div className="space-y-2">
                  {compatibilityData.pairwise_breakdowns.map((pair, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-warm-50 rounded-xl border border-warm-200 flex items-center justify-between text-xs"
                    >
                      <div className="font-semibold text-charcoal">
                        {pair.user_one_name} ↔ {pair.user_two_name}
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-forest">{Math.round(pair.score)}%</span>
                        {pair.dealbreakers_cleared ? (
                          <CheckCircle2 className="w-4 h-4 text-forest" />
                        ) : (
                          <ShieldAlert className="w-4 h-4 text-rose-500" />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {compatibilityData.shared_strengths && compatibilityData.shared_strengths.length > 0 && (
              <div>
                <h4 className="text-xs font-bold text-charcoal uppercase mb-2">Shared Cohesion Strengths</h4>
                <div className="flex flex-wrap gap-1.5">
                  {compatibilityData.shared_strengths.map((str, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 bg-pale-green/40 text-forest border border-brand-200 text-xs rounded-lg font-semibold"
                    >
                      {str}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="py-6 text-center text-xs text-charcoal-muted">
            No compatibility breakdown available yet.
          </div>
        )}
      </Modal>

      {/* Group Wishlist Modal */}
      <Modal
        isOpen={wishlistModalOpen}
        onClose={() => setWishlistModalOpen(false)}
        title={wishlistGroup ? `${wishlistGroup.name} — Property Wishlist` : "Group Wishlist"}
        description="Collaborative property shortlist voted on by group members."
      >
        {wishlistGroup && (
          <div className="space-y-4 mt-2">
            {/* Add Property to Wishlist Form */}
            <form onSubmit={handleAddPropertyToWishlist} className="flex gap-2">
              <Input
                placeholder="Enter Property UUID to shortlist..."
                value={newPropertyId}
                onChange={(e) => setNewPropertyId(e.target.value)}
                className="text-xs"
              />
              <Button type="submit" size="sm" variant="primary" isLoading={isAddingProperty} className="shrink-0">
                Add Flat
              </Button>
            </form>

            {(!wishlistGroup.wishlist || wishlistGroup.wishlist.length === 0) ? (
              <div className="text-center py-8">
                <Bookmark className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                <h4 className="font-bold text-charcoal text-sm">Wishlist is empty</h4>
                <p className="text-xs text-charcoal-muted mt-1">
                  Add properties using the input above or shortlist from property listings to vote as a team.
                </p>
              </div>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {wishlistGroup.wishlist.map((item) => (
                  <GroupWishlistCard
                    key={item.id}
                    propertyId={item.property_id}
                    title="Shortlisted Syndicate Flat"
                    locality={wishlistGroup.target_city}
                    monthlyRent={Math.round(
                      wishlistGroup.target_budget_total / Math.max(1, wishlistGroup.members.length)
                    )}
                    votes={(item.votes as any) || {}}
                    currentUserId={user?.id || ""}
                    onVote={(propId, vote) => handleVoteWishlist(propId, vote)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Invite Member Modal */}
      <Modal
        isOpen={inviteModalOpen}
        onClose={() => setInviteModalOpen(false)}
        title="Invite Member to Syndicate"
        description="Invite a flatmate by their User ID to join your hunting group."
      >
        {inviteMessage ? (
          <div className="text-center py-6">
            <CheckCircle2 className="w-12 h-12 text-forest mx-auto mb-2" />
            <h4 className="font-bold text-charcoal text-base">{inviteMessage}</h4>
          </div>
        ) : (
          <form onSubmit={handleSendMemberInvite} className="space-y-4 mt-2">
            <Input
              label="Flatmate User ID (UUID)"
              required
              value={inviteUserId}
              onChange={(e) => setInviteUserId(e.target.value)}
              placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
            />
            <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isInviting}>
              Send Syndicate Invitation
            </Button>
          </form>
        )}
      </Modal>
    </div>
  );
}
