"use client";

import React from "react";
import Link from "next/link";
import { useMatches } from "@/hooks/useMatches";
import { useAuth } from "@/hooks/useAuth";
import { Card, Avatar, Button, MatchScoreBadge } from "@flatmate/ui";
import { formatCurrency } from "@/lib/utils";
import { Sparkles, MessageSquare, ArrowRight, CheckCircle2 } from "lucide-react";

export default function MatchesPage() {
  const { isAuthenticated } = useAuth();
  const { matches, isLoading, error } = useMatches(10);

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <Sparkles className="w-12 h-12 text-indigo-600 mx-auto mb-3" />
        <h2 className="text-2xl font-bold text-slate-900">Sign in to view your algorithmic matches</h2>
        <p className="text-sm text-slate-500 mt-2 max-w-md mx-auto">
          We match your 64-dimensional lifestyle embedding vector with thousands of potential roommates.
        </p>
        <Link href="/login" className="inline-block mt-6">
          <Button variant="primary">Sign In Now</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-1.5 bg-indigo-50 text-indigo-700 text-xs font-semibold px-3 py-1 rounded-full mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Vector Recommendations</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Your Top Lifestyle Matches</h1>
          <p className="text-slate-500 text-sm mt-1">
            Ranked by multi-factor cosine vector similarity and hard habit dealbreakers.
          </p>
        </div>

        <Link href="/dashboard">
          <Button variant="outline" size="sm">
            Update My Lifestyle Quiz
          </Button>
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-4 animate-pulse">
          {[1, 2, 3].map((n) => (
            <div key={n} className="bg-slate-200 h-40 rounded-2xl" />
          ))}
        </div>
      ) : matches.length === 0 ? (
        <Card className="p-12 text-center max-w-lg mx-auto">
          <Sparkles className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No match candidates found yet</h3>
          <p className="text-xs text-slate-500 mt-1">
            Ensure your lifestyle questionnaire is completed to activate vector comparisons.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {matches.map((item) => (
            <Card key={item.profile.id} className="p-6 border-slate-200/80 hover:shadow-md transition-shadow">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center space-x-4">
                  <Avatar
                    src={item.profile.avatar_url}
                    alt={item.profile.display_name}
                    size="lg"
                    isVerified={true}
                  />
                  <div>
                    <div className="flex items-center space-x-2">
                      <h3 className="font-bold text-slate-900 text-lg">{item.profile.display_name}</h3>
                      <MatchScoreBadge score={item.match_score.overall_score} size="md" />
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {item.profile.occupation || "Professional"} • Budget: {formatCurrency(item.profile.budget_min)} - {formatCurrency(item.profile.budget_max)}/mo
                    </p>
                    <p className="text-xs text-slate-600 mt-2 line-clamp-1 max-w-xl">
                      {item.profile.bio}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3 self-end md:self-center">
                  <Link href={`/flatmates/${item.profile.user_id}`}>
                    <Button variant="outline" size="sm" className="gap-1">
                      <span>View Breakdown</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Button>
                  </Link>
                  <Link href="/messages">
                    <Button variant="primary" size="sm" className="gap-1">
                      <MessageSquare className="w-3.5 h-3.5" />
                      <span>Chat</span>
                    </Button>
                  </Link>
                </div>
              </div>

              {/* Shared habits pills */}
              <div className="mt-4 pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                <span className="font-semibold text-slate-500">Alignment:</span>
                <span className="bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-md font-medium">
                  {item.match_score.cleanliness_alignment}% Cleanliness
                </span>
                <span className="bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-md font-medium">
                  {item.match_score.schedule_alignment}% Schedule
                </span>
                <span className="bg-purple-50 text-purple-700 px-2 py-0.5 rounded-md font-medium">
                  {item.match_score.social_alignment}% Social Vibe
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
