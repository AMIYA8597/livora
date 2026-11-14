"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useMatches } from "@/hooks/useMatches";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/api-client";
import { Card, Avatar, Button, MatchScoreBadge, Badge, Skeleton, EmptyState } from "@flatmate/ui";
import { MutualMatchItemResponse } from "@flatmate/contracts";
import { formatCurrency } from "@/lib/utils";
import {
  Sparkles,
  MessageSquare,
  ArrowRight,
  Heart,
  Bookmark,
  Users,
  CheckCircle2,
  XCircle,
  ThumbsUp,
} from "lucide-react";

export default function MatchesPage() {
  const { isAuthenticated } = useAuth();
  const { matches, isLoading, error } = useMatches(15);
  const [activeTab, setActiveTab] = useState<"recommendations" | "mutual">("recommendations");
  const [mutualMatches, setMutualMatches] = useState<MutualMatchItemResponse[]>([]);
  const [loadingMutual, setLoadingMutual] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  useEffect(() => {
    async function loadMutualMatches() {
      if (!isAuthenticated) return;
      try {
        setLoadingMutual(true);
        const data = await apiClient<MutualMatchItemResponse[]>("/matching/matches");
        setMutualMatches(data || []);
      } catch (err) {
        console.error("Failed to load mutual matches:", err);
      } finally {
        setLoadingMutual(false);
      }
    }
    if (activeTab === "mutual") {
      loadMutualMatches();
    }
  }, [activeTab, isAuthenticated]);

  const handleInteraction = async (targetUserId: string, action: "like" | "save" | "pass") => {
    try {
      const res = await apiClient<{ action: string; is_mutual_match: boolean }>("/matching/interactions", {
        method: "POST",
        body: JSON.stringify({
          target_user_id: targetUserId,
          action,
        }),
      });
      if (res.is_mutual_match) {
        setActionNotice("It's a Mutual Match! Switched to Mutual Matches tab.");
        setActiveTab("mutual");
      } else {
        setActionNotice(
          action === "like"
            ? "Candidate liked!"
            : action === "pass"
            ? "Candidate passed."
            : "Candidate saved to shortlist."
        );
      }
      setTimeout(() => setActionNotice(null), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to record interaction");
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-pale-green/40 text-forest flex items-center justify-center mx-auto shadow-sm">
          <Sparkles className="w-8 h-8" />
        </div>
        <h2 className="text-2xl font-bold text-charcoal">Sign in to view your lifestyle matches</h2>
        <p className="text-sm text-charcoal-muted max-w-md mx-auto leading-relaxed">
          We match your 10-dimension questionnaire and vectors with potential roommates in your target cities.
        </p>
        <div className="pt-2">
          <Link href="/login">
            <Button variant="primary" size="md">
              Sign In Now
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-1.5 bg-pale-green/40 text-forest text-xs font-semibold px-3 py-1 rounded-full mb-2 border border-brand-200">
            <Sparkles className="w-3.5 h-3.5 text-secondary-green" />
            <span>AI Vector Recommendations</span>
          </div>
          <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">
            Lifestyle Compatibility Matches
          </h1>
          <p className="text-charcoal-muted text-sm mt-1">
            Ranked by multi-factor cosine vector similarity and 10-dimension habit dealbreakers.
          </p>
        </div>

        <Link href="/profile">
          <Button variant="outline" size="sm" className="font-semibold text-charcoal">
            Update My Lifestyle Preferences
          </Button>
        </Link>
      </div>

      {actionNotice && (
        <div className="p-4 bg-pale-green/30 border border-brand-200 text-forest rounded-2xl text-xs font-semibold flex items-center space-x-2 animate-in fade-in duration-150">
          <CheckCircle2 className="w-4 h-4 text-forest shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex space-x-4 border-b border-warm-200">
        <button
          onClick={() => setActiveTab("recommendations")}
          className={`pb-3 px-3 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === "recommendations"
              ? "border-forest text-forest"
              : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          Algorithmic Recommendations ({matches.length})
        </button>
        <button
          onClick={() => setActiveTab("mutual")}
          className={`pb-3 px-3 text-sm font-semibold border-b-2 transition-colors flex items-center space-x-1.5 ${
            activeTab === "mutual"
              ? "border-forest text-forest"
              : "border-transparent text-charcoal-muted hover:text-charcoal"
          }`}
        >
          <Heart className="w-4 h-4 text-rose-500 fill-rose-500" />
          <span>Mutual Matches ({mutualMatches.length})</span>
        </button>
      </div>

      {/* Recommendations Tab */}
      {activeTab === "recommendations" && (
        <>
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton variant="card" height={160} />
              <Skeleton variant="card" height={160} />
              <Skeleton variant="card" height={160} />
            </div>
          ) : matches.length === 0 ? (
            <EmptyState
              icon={Sparkles}
              title="No match candidates found yet"
              description="Complete or update your 10-dimension questionnaire to activate pairwise vector comparisons."
              actionLabel="Complete Questionnaire"
              onAction={() => (window.location.href = "/profile")}
            />
          ) : (
            <div className="space-y-4">
              {matches.map((item) => {
                const factors = item.match_score.factors || {};
                const cleanlinessVal = item.match_score.cleanliness_alignment ?? factors.cleanliness ?? 75;
                const scheduleVal = item.match_score.schedule_alignment ?? factors.sleep_schedule ?? 80;
                const socialVal = item.match_score.social_alignment ?? factors.guests_and_social ?? 75;

                return (
                  <Card key={item.profile.id} className="p-6 border-warm-200 hover:shadow-md transition-shadow bg-white">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div className="flex items-center space-x-4">
                        <Avatar
                          src={item.profile.avatar_url || undefined}
                          alt={item.profile.display_name}
                          size="lg"
                          isVerified={true}
                        />
                        <div>
                          <div className="flex items-center space-x-2">
                            <h3 className="font-bold text-charcoal text-lg">
                              {item.profile.display_name}
                            </h3>
                            <MatchScoreBadge score={item.match_score.overall_score} size="md" />
                          </div>
                          <p className="text-xs text-charcoal-muted mt-0.5">
                            {item.profile.occupation || "Professional"} • Budget: {formatCurrency(item.profile.budget_min, "INR")} - {formatCurrency(item.profile.budget_max, "INR")}/mo
                          </p>
                          <p className="text-xs text-charcoal-muted mt-2 line-clamp-1 max-w-xl">
                            {item.profile.bio || "Looking for a compatible roommate and comfortable space."}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 self-end md:self-center">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="gap-1 text-charcoal-muted hover:text-charcoal"
                          onClick={() => handleInteraction(item.profile.user_id, "pass")}
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          <span>Pass</span>
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-1 border-brand-200 text-forest hover:bg-pale-green/30"
                          onClick={() => handleInteraction(item.profile.user_id, "like")}
                        >
                          <ThumbsUp className="w-3.5 h-3.5" />
                          <span>Like</span>
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-1 border-warm-200"
                          onClick={() => handleInteraction(item.profile.user_id, "save")}
                        >
                          <Bookmark className="w-3.5 h-3.5 text-forest" />
                          <span>Save</span>
                        </Button>
                        <Link href={`/flatmates/${item.profile.user_id}`}>
                          <Button variant="primary" size="sm" className="gap-1">
                            <span>View Radar</span>
                            <ArrowRight className="w-3.5 h-3.5" />
                          </Button>
                        </Link>
                      </div>
                    </div>

                    {/* Alignment pills */}
                    <div className="mt-4 pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2 text-xs text-charcoal">
                      <span className="font-semibold text-charcoal-muted">Alignment:</span>
                      <span className="bg-pale-green/40 text-forest px-2.5 py-0.5 rounded-md font-semibold border border-brand-200">
                        {cleanlinessVal}% Cleanliness
                      </span>
                      <span className="bg-pale-green/40 text-forest px-2.5 py-0.5 rounded-md font-semibold border border-brand-200">
                        {scheduleVal}% Schedule
                      </span>
                      <span className="bg-pale-green/40 text-forest px-2.5 py-0.5 rounded-md font-semibold border border-brand-200">
                        {socialVal}% Social Vibe
                      </span>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Mutual Matches Tab */}
      {activeTab === "mutual" && (
        <>
          {loadingMutual ? (
            <div className="space-y-4">
              <Skeleton variant="card" height={100} />
              <Skeleton variant="card" height={100} />
            </div>
          ) : mutualMatches.length === 0 ? (
            <EmptyState
              icon={Heart}
              title="No mutual matches yet"
              description="Like other seekers in the recommendations tab. When they like you back, you will see them here with direct chat unlocked!"
              actionLabel="Browse Recommendations"
              onAction={() => setActiveTab("recommendations")}
            />
          ) : (
            <div className="space-y-4">
              {mutualMatches.map((m) => (
                <Card key={m.id} className="p-5 border-warm-200 flex items-center justify-between gap-4 bg-white">
                  <div className="flex items-center space-x-4">
                    <Avatar
                      src={m.partner_avatar || undefined}
                      alt={m.partner_name}
                      size="lg"
                      isVerified={true}
                    />
                    <div>
                      <div className="flex items-center space-x-2">
                        <h4 className="font-bold text-charcoal text-base">{m.partner_name}</h4>
                        <span className="text-xs bg-pale-green/50 text-forest border border-brand-200 px-2.5 py-0.5 rounded-full font-bold">
                          {Math.round(m.compatibility_score)}% Mutual Fit
                        </span>
                      </div>
                      <p className="text-xs text-charcoal-muted mt-0.5">
                        {m.partner_occupation || "Verified Seeker"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Link href={`/flatmates/${m.partner_id}`}>
                      <Button variant="outline" size="sm">
                        View Profile
                      </Button>
                    </Link>
                    <Link href="/messages">
                      <Button variant="primary" size="sm" className="gap-1.5">
                        <MessageSquare className="w-3.5 h-3.5" />
                        <span>Chat Now</span>
                      </Button>
                    </Link>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
