"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ProfileDTO, ScoreBreakdown, GroupDTO } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { formatCurrency } from "@/lib/utils";
import { upgradeFrom, type UpgradeHint } from "@/lib/billing-model";
import { UpgradePrompt } from "@/components/billing/UpgradePrompt";
import { InlineNotice } from "@/components/states/InlineNotice";
import { useAuth } from "@/hooks/useAuth";
import { CompatibilityRadar } from "@/components/CompatibilityRadar";
import { Avatar, Button, Card, Modal, Input } from "@flatmate/ui";
import {
  Briefcase, MapPin, MessageSquare, UserPlus, ShieldCheck, Sun, Moon,
  Utensils, Cigarette, Dog, Sparkles, ArrowLeft, Heart, Bookmark,
  ShieldAlert, Flag, CheckCircle2
} from "lucide-react";

export default function SeekerProfileDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated, user } = useAuth();
  const targetUserId = params.id as string;

  const [profile, setProfile] = useState<ProfileDTO | null>(null);
  const [score, setScore] = useState<ScoreBreakdown | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [interactionSuccess, setInteractionSuccess] = useState<string | null>(null);
  const [interactionError, setInteractionError] = useState<string | null>(null);
  const [upgrade, setUpgrade] = useState<UpgradeHint | null>(null);

  // Group invite modal state
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [myGroups, setMyGroups] = useState<GroupDTO[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string>("");
  const [isInviting, setIsInviting] = useState(false);
  const [inviteSuccess, setInviteSuccess] = useState(false);

  // Report modal state
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [reportReason, setReportReason] = useState("inappropriate_behavior");
  const [reportDescription, setReportDescription] = useState("");
  const [isSubmittingReport, setIsSubmittingReport] = useState(false);
  const [reportSuccess, setReportSuccess] = useState(false);

  useEffect(() => {
    async function loadData() {
      try {
        setIsLoading(true);
        const p = await apiClient<ProfileDTO>(`/profiles/${targetUserId}`);
        setProfile(p);

        // Fetch compatibility score only if user is authenticated and not viewing self
        if (typeof window !== "undefined" && localStorage.getItem("flatmate_access_token")) {
          try {
            const s = await apiClient<ScoreBreakdown>(`/matching/compatibility/${targetUserId}`);
            setScore(s);
          } catch {
            setScore(null);
          }
        }
      } catch (err) {
        console.error("Failed to load profile:", err);
      } finally {
        setIsLoading(false);
      }
    }
    if (targetUserId) loadData();
  }, [targetUserId]);

  const handleStartChat = async () => {
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    try {
      await apiClient<{ conversation_id: string }>("/messaging/conversations", {
        method: "POST",
        body: JSON.stringify({
          participant_user_ids: [targetUserId],
          type: "direct",
        }),
      });
      router.push("/messages");
    } catch {
      router.push("/messages");
    }
  };

  const handleInteraction = async (action: "like" | "save") => {
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    setInteractionError(null);
    try {
      const res = await apiClient<{ action: string; is_mutual_match: boolean }>("/matching/interactions", {
        method: "POST",
        body: JSON.stringify({
          target_user_id: targetUserId,
          action,
        }),
      });
      if (res.is_mutual_match) {
        setInteractionSuccess("It's a Mutual Match! You can now message directly.");
      } else {
        setInteractionSuccess(action === "like" ? "Profile liked!" : "Profile saved to shortlist.");
      }
      setTimeout(() => setInteractionSuccess(null), 3000);
    } catch (err) {
      const hint = upgradeFrom(err);
      if (hint) setUpgrade(hint);
      else setInteractionError(err instanceof Error ? err.message : "Couldn't record that. Please try again.");
    }
  };

  const handleOpenInviteModal = async () => {
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }
    try {
      const groups = await apiClient<GroupDTO[]>("/groups/");
      const createdByMe = groups.filter((g) => g.creator_id === user?.id);
      setMyGroups(createdByMe);
      if (createdByMe.length > 0) {
        setSelectedGroupId(createdByMe[0].id);
      }
      setIsInviteModalOpen(true);
    } catch (err: any) {
      alert(err.message || "Failed to load groups");
    }
  };

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedGroupId) return;
    try {
      setIsInviting(true);
      await apiClient(`/groups/${selectedGroupId}/members`, {
        method: "POST",
        body: JSON.stringify({
          user_id: targetUserId,
          role: "member",
        }),
      });
      setInviteSuccess(true);
      setTimeout(() => {
        setIsInviteModalOpen(false);
        setInviteSuccess(false);
      }, 2000);
    } catch (err: any) {
      alert(err.message || "Failed to send group invitation");
    } finally {
      setIsInviting(false);
    }
  };

  const handleReportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSubmittingReport(true);
      await apiClient("/moderation/reports", {
        method: "POST",
        body: JSON.stringify({
          target_type: "user",
          target_id: targetUserId,
          reason: reportReason,
          description: reportDescription || undefined,
        }),
      });
      setReportSuccess(true);
      setTimeout(() => {
        setIsReportModalOpen(false);
        setReportSuccess(false);
      }, 2000);
    } catch (err: any) {
      alert(err.message || "Failed to submit moderation report");
    } finally {
      setIsSubmittingReport(false);
    }
  };

  const handleBlockUser = async () => {
    if (!confirm("Are you sure you want to block this user? You will no longer see each other or exchange messages.")) {
      return;
    }
    try {
      await apiClient(`/moderation/blocks/${targetUserId}`, { method: "POST" });
      alert("User blocked successfully.");
      router.push("/flatmates");
    } catch (err: any) {
      alert(err.message || "Failed to block user");
    }
  };

  if (isLoading) {
    return <div className="max-w-7xl mx-auto px-4 py-20 text-center text-slate-500">Loading profile...</div>;
  }

  if (!profile) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <h2 className="text-xl font-bold text-slate-900">Profile not found</h2>
        <Button variant="outline" className="mt-4" onClick={() => router.push("/flatmates")}>
          Back to Directory
        </Button>
      </div>
    );
  }

  const traits = profile.lifestyle_traits || ({} as any);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div className="flex items-center justify-between">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center text-xs font-semibold text-slate-600 hover:text-indigo-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </button>

        {isAuthenticated && user?.id !== targetUserId && (
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsReportModalOpen(true)}
              className="text-xs text-slate-400 hover:text-rose-600 flex items-center gap-1 font-medium transition-colors"
            >
              <Flag className="w-3.5 h-3.5" />
              <span>Report</span>
            </button>
            <span className="text-slate-300">•</span>
            <button
              onClick={handleBlockUser}
              className="text-xs text-slate-400 hover:text-rose-600 font-medium transition-colors"
            >
              Block
            </button>
          </div>
        )}
      </div>

      {upgrade && <UpgradePrompt hint={upgrade} onDismiss={() => setUpgrade(null)} />}
      {interactionError && <InlineNotice tone="error">{interactionError}</InlineNotice>}
      {interactionSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-2xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{interactionSuccess}</span>
        </div>
      )}

      {/* Profile Header Hero */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/80 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="flex items-center space-x-5">
          <Avatar
            src={profile.avatar_url || undefined}
            alt={profile.display_name}
            size="xl"
            isVerified={true}
          />
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">{profile.display_name}</h1>
              <span title="Verified Identity">
                <ShieldCheck className="w-6 h-6 text-emerald-500" />
              </span>
            </div>
            <p className="text-sm text-slate-500 flex items-center space-x-1.5 mt-1">
              <Briefcase className="w-4 h-4 text-slate-400" />
              <span>{profile.occupation || profile.designation || "Professional"}</span>
            </p>
            <p className="text-xs text-slate-500 flex items-center space-x-1.5 mt-1">
              <MapPin className="w-4 h-4 text-slate-400" />
              <span>Preferred: {profile.preferred_locations?.join(", ") || "Flexible City Locations"}</span>
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          <Button
            variant="outline"
            size="md"
            className="gap-1.5 text-rose-600 hover:text-rose-700 hover:bg-rose-50 border-rose-200"
            onClick={() => handleInteraction("like")}
          >
            <Heart className="w-4 h-4" />
            <span>Like</span>
          </Button>

          <Button
            variant="outline"
            size="md"
            className="gap-1.5"
            onClick={() => handleInteraction("save")}
          >
            <Bookmark className="w-4 h-4 text-indigo-600" />
            <span>Save</span>
          </Button>

          <Button variant="primary" size="md" className="gap-2" onClick={handleStartChat}>
            <MessageSquare className="w-4 h-4" />
            <span>Chat Directly</span>
          </Button>

          <Button variant="secondary" size="md" className="gap-2" onClick={handleOpenInviteModal}>
            <UserPlus className="w-4 h-4" />
            <span>Invite to Group</span>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Bio & Lifestyle Traits */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="p-6 border-slate-200/80">
            <h3 className="font-bold text-slate-900 text-lg mb-2">About Me</h3>
            <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">
              {profile.bio || "No detailed bio added yet."}
            </p>

            <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between text-sm">
              <span className="text-slate-500">Monthly Budget Range:</span>
              <span className="font-bold text-slate-900 text-base">
                {formatCurrency(profile.budget_min, "INR")} - {formatCurrency(profile.budget_max, "INR")}/mo
              </span>
            </div>
          </Card>

          {/* Lifestyle Matrix */}
          <Card className="p-6 border-slate-200/80 space-y-4">
            <h3 className="font-bold text-slate-900 text-lg">Living Habits & Lifestyle</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="p-3 bg-slate-50 rounded-xl flex items-center space-x-3 border border-slate-100">
                <Sun className="w-5 h-5 text-amber-500 shrink-0" />
                <div>
                  <span className="text-[11px] font-bold text-slate-400 uppercase">Sleep Pattern</span>
                  <p className="text-xs font-semibold text-slate-800 capitalize">
                    {traits.sleep_schedule?.replace(/_/g, " ") || "Flexible"}
                  </p>
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl flex items-center space-x-3 border border-slate-100">
                <Sparkles className="w-5 h-5 text-indigo-500 shrink-0" />
                <div>
                  <span className="text-[11px] font-bold text-slate-400 uppercase">Cleanliness Level</span>
                  <p className="text-xs font-semibold text-slate-800">
                    {traits.cleanliness_level ? `${traits.cleanliness_level} / 5` : "3 / 5 (Moderate)"}
                  </p>
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl flex items-center space-x-3 border border-slate-100">
                <Utensils className="w-5 h-5 text-emerald-500 shrink-0" />
                <div>
                  <span className="text-[11px] font-bold text-slate-400 uppercase">Diet</span>
                  <p className="text-xs font-semibold text-slate-800 capitalize">
                    {traits.diet_preference || traits.diet || "Omnivore"}
                  </p>
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl flex items-center space-x-3 border border-slate-100">
                <Cigarette className="w-5 h-5 text-rose-500 shrink-0" />
                <div>
                  <span className="text-[11px] font-bold text-slate-400 uppercase">Smoking Policy</span>
                  <p className="text-xs font-semibold text-slate-800 capitalize">
                    {traits.smoking?.replace(/_/g, " ") || "Never"}
                  </p>
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl flex items-center space-x-3 border border-slate-100">
                <Dog className="w-5 h-5 text-purple-500 shrink-0" />
                <div>
                  <span className="text-[11px] font-bold text-slate-400 uppercase">Pets</span>
                  <p className="text-xs font-semibold text-slate-800 capitalize">
                    {traits.pet_preference?.replace(/_/g, " ") || traits.pets?.replace(/_/g, " ") || "Cats OK"}
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Column: Compatibility Radar */}
        <div>
          <CompatibilityRadar score={score} />
        </div>
      </div>

      {/* Group Invite Modal */}
      <Modal
        isOpen={isInviteModalOpen}
        onClose={() => setIsInviteModalOpen(false)}
        title="Invite to Hunting Syndicate"
        description="Select which of your active groups to invite this flatmate to."
      >
        {inviteSuccess ? (
          <div className="text-center py-6">
            <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-2" />
            <h4 className="font-bold text-slate-900 text-base">Invitation Dispatched!</h4>
            <p className="text-xs text-slate-500 mt-1">They have been added to your syndicate roster.</p>
          </div>
        ) : myGroups.length === 0 ? (
          <div className="text-center py-6">
            <UserPlus className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <p className="text-xs text-slate-600 mb-4">You have not created any hunting syndicates yet.</p>
            <Button variant="primary" size="sm" onClick={() => router.push("/groups")}>
              Create a Group First
            </Button>
          </div>
        ) : (
          <form onSubmit={handleSendInvite} className="space-y-4 mt-2">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Select Group</label>
              <select
                value={selectedGroupId}
                onChange={(e) => setSelectedGroupId(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {myGroups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} ({g.target_city})
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isInviting}>
              Send Invitation
            </Button>
          </form>
        )}
      </Modal>

      {/* Moderation Report Modal */}
      <Modal
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
        title="Report Seeker Profile"
        description="Our safety team investigates all reported profiles within 24 hours."
      >
        {reportSuccess ? (
          <div className="text-center py-6">
            <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto mb-2" />
            <h4 className="font-bold text-slate-900 text-base">Report Submitted</h4>
            <p className="text-xs text-slate-500 mt-1">Thank you for helping keep the flatmate network safe.</p>
          </div>
        ) : (
          <form onSubmit={handleReportSubmit} className="space-y-4 mt-2">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Reason for Report</label>
              <select
                value={reportReason}
                onChange={(e) => setReportReason(e.target.value)}
                className="w-full text-sm border border-slate-300 rounded-xl p-2.5 bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="inappropriate_behavior">Inappropriate or Harassing Messages</option>
                <option value="fraud_or_scam">Suspected Advance Payment Scam</option>
                <option value="fake_profile">Fake Profile or Impersonation</option>
                <option value="discrimination">Discriminatory Demands</option>
                <option value="other">Other Safety Concern</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Details (Optional)</label>
              <textarea
                rows={3}
                value={reportDescription}
                onChange={(e) => setReportDescription(e.target.value)}
                placeholder="Provide any relevant context for our safety moderators..."
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isSubmittingReport}>
              Submit Safety Report
            </Button>
          </form>
        )}
      </Modal>
    </div>
  );
}
