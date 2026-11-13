"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ProfileDTO, ScoreBreakdown } from "@flatmate/contracts";
import { apiClient } from "@/lib/api-client";
import { formatCurrency } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";
import { CompatibilityRadar } from "@/components/CompatibilityRadar";
import { Avatar, Button, Card, Badge } from "@flatmate/ui";
import { Briefcase, MapPin, MessageSquare, UserPlus, ShieldCheck, Sun, Moon, Utensils, Cigarette, Dog, Sparkles, ArrowLeft } from "lucide-react";

export default function SeekerProfileDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const targetUserId = params.id as string;

  const [profile, setProfile] = useState<ProfileDTO | null>(null);
  const [score, setScore] = useState<ScoreBreakdown | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        setIsLoading(true);
        const p = await apiClient<ProfileDTO>(`/profiles/${targetUserId}`);
        setProfile(p);

        // Fetch compatibility score if user logged in
        if (localStorage.getItem("flatmate_access_token")) {
          try {
            const s = await apiClient<ScoreBreakdown>(`/matching/compatibility/${targetUserId}`);
            setScore(s);
          } catch {
            // Default mock breakdown if calculation endpoint not available for guest
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
      const res = await apiClient<{ conversation_id: string }>("/messaging/conversations", {
        method: "POST",
        body: JSON.stringify({
          participant_user_ids: [targetUserId],
          type: "direct",
        }),
      });
      router.push("/messages");
    } catch (err: any) {
      router.push("/messages");
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

  // Fallback demo score if not calculated
  const displayScore: ScoreBreakdown = score || {
    overall_score: 94.0,
    lifestyle_score: 92,
    cleanliness_alignment: 96,
    schedule_alignment: 95,
    social_alignment: 90,
    budget_alignment: 95,
    dealbreakers_cleared: true,
    shared_interests: ["Early morning routine", "Quiet study hours", "Tidy kitchen"],
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <button
        onClick={() => router.back()}
        className="inline-flex items-center text-xs font-semibold text-slate-600 hover:text-indigo-600 transition-colors"
      >
        <ArrowLeft className="w-4 h-4 mr-1" />
        Back
      </button>

      {/* Profile Header Hero */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/80 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="flex items-center space-x-5">
          <Avatar
            src={profile.avatar_url}
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
              <span>{profile.occupation || "Professional"}</span>
            </p>
            <p className="text-xs text-slate-500 flex items-center space-x-1.5 mt-1">
              <MapPin className="w-4 h-4 text-slate-400" />
              <span>Seeking in: {profile.preferred_locations?.join(", ") || "San Francisco"}</span>
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-3 w-full md:w-auto">
          <Button variant="primary" size="lg" className="flex-1 md:flex-none gap-2" onClick={handleStartChat}>
            <MessageSquare className="w-4 h-4" />
            <span>Chat Directly</span>
          </Button>
          <Button variant="secondary" size="lg" className="flex-1 md:flex-none gap-2">
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
                {formatCurrency(profile.budget_min)} - {formatCurrency(profile.budget_max)}/mo
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
                    {traits.sleep_schedule?.replace(/_/g, " ") || "Early Bird"}
                  </p>
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl flex items-center space-x-3 border border-slate-100">
                <Sparkles className="w-5 h-5 text-indigo-500 shrink-0" />
                <div>
                  <span className="text-[11px] font-bold text-slate-400 uppercase">Cleanliness Level</span>
                  <p className="text-xs font-semibold text-slate-800">
                    {traits.cleanliness_level || 5} / 5 (Ultra-tidy)
                  </p>
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl flex items-center space-x-3 border border-slate-100">
                <Utensils className="w-5 h-5 text-emerald-500 shrink-0" />
                <div>
                  <span className="text-[11px] font-bold text-slate-400 uppercase">Diet</span>
                  <p className="text-xs font-semibold text-slate-800 capitalize">
                    {traits.diet || "Omnivore"}
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
                    {traits.pets?.replace(/_/g, " ") || "Cats OK"}
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Column: Compatibility Radar */}
        <div>
          <CompatibilityRadar score={displayScore} />
        </div>
      </div>
    </div>
  );
}
