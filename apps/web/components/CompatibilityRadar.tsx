"use client";

import React, { useState } from "react";
import { ScoreBreakdown } from "@flatmate/contracts";
import { Sparkles, ShieldAlert, CheckCircle2, ChevronDown, ChevronUp, AlertCircle, Info } from "lucide-react";
import { Badge } from "@flatmate/ui";

export interface CompatibilityRadarProps {
  score?: ScoreBreakdown | null;
}

export const CompatibilityRadar: React.FC<CompatibilityRadarProps> = ({ score }) => {
  const [expanded, setExpanded] = useState(true);

  if (!score) {
    return (
      <div className="bg-white rounded-2xl p-6 border border-warm-200 shadow-xs text-center py-10">
        <Sparkles className="w-10 h-10 text-charcoal-muted mx-auto mb-2 opacity-50" />
        <h4 className="font-bold text-charcoal text-base">Compatibility Analysis</h4>
        <p className="text-xs text-charcoal-muted mt-1 max-w-xs mx-auto leading-relaxed">
          Log in and complete your lifestyle questionnaire to calculate 10-dimension compatibility with this flatmate.
        </p>
      </div>
    );
  }

  const factors = score.factors || {};
  const explanations = score.explanations || {};

  const dimensions = [
    {
      key: "cleanliness",
      name: "Cleanliness & Household Habits",
      value: factors.cleanliness ?? score.cleanliness_alignment ?? 75,
      explanation: explanations.cleanliness || "Tidiness and chore philosophy alignment.",
    },
    {
      key: "sleep_schedule",
      name: "Sleep Schedules & Quiet Hours",
      value: factors.sleep_schedule ?? score.schedule_alignment ?? 80,
      explanation: explanations.sleep_schedule || "Sleep patterns and morning/night routines.",
    },
    {
      key: "working_schedule",
      name: "Work Routine & WFH Schedule",
      value: factors.working_schedule ?? 85,
      explanation: explanations.working_schedule || "Remote, hybrid, or in-office occupancy.",
    },
    {
      key: "food_and_cooking",
      name: "Diet Preferences & Cooking",
      value: factors.food_and_cooking ?? 80,
      explanation: explanations.food_and_cooking || "Kitchen and dietary habits for mutual comfort.",
    },
    {
      key: "lifestyle",
      name: "Smoking & Substance Habits",
      value: factors.lifestyle ?? score.lifestyle_score ?? 75,
      explanation: explanations.lifestyle || "Household smoking and lifestyle harmony.",
    },
    {
      key: "noise_and_lighting",
      name: "Noise Tolerance & Lighting",
      value: factors.noise_and_lighting ?? 80,
      explanation: explanations.noise_and_lighting || "Sound environment and lighting preferences.",
    },
    {
      key: "guests_and_social",
      name: "Guests Policy & Social Rhythm",
      value: factors.guests_and_social ?? score.social_alignment ?? 75,
      explanation: explanations.guests_and_social || "Visitor frequency and household social battery.",
    },
    {
      key: "budget",
      name: "Budget Range Alignment",
      value: factors.budget ?? score.budget_alignment ?? 80,
      explanation: explanations.budget || "Monthly rent budget overlap.",
    },
    {
      key: "location",
      name: "Locality & Area Preference",
      value: factors.location ?? 85,
      explanation: explanations.location || "Target neighborhoods and city preference.",
    },
    {
      key: "professional_domain",
      name: "Career Rhythm & Professional Domain",
      value: factors.professional_domain ?? 80,
      explanation: explanations.professional_domain || "Career schedules and professional domains.",
    },
  ];

  const getTierColor = (val: number) => {
    if (val >= 80) return "bg-forest";
    if (val >= 60) return "bg-secondary-green";
    if (val >= 40) return "bg-amber-500";
    return "bg-rose-500";
  };

  const getTierLabel = (val: number) => {
    if (val >= 80) return "Strong Alignment";
    if (val >= 60) return "Moderate Fit";
    if (val >= 40) return "Slight Difference";
    return "Potential Friction";
  };

  return (
    <div className="bg-white rounded-3xl p-6 border border-warm-200 shadow-xs space-y-6">
      {/* Header with Score */}
      <div className="flex items-center justify-between pb-4 border-b border-warm-200">
        <div>
          <div className="flex items-center space-x-2">
            <Sparkles className="w-5 h-5 text-forest" />
            <h3 className="font-bold text-charcoal text-lg">Compatibility Analysis</h3>
          </div>
          <p className="text-xs text-charcoal-muted mt-0.5">
            Vector-computed across 10 behavioral dimensions
          </p>
        </div>

        <div className="text-right">
          <div className="text-3xl font-extrabold text-forest">
            {Math.round(score.overall_score)}%
          </div>
          <span className="text-[10px] font-bold text-charcoal-muted uppercase tracking-wider block">
            Overall Fit
          </span>
        </div>
      </div>

      {/* Dealbreaker Status */}
      {score.dealbreakers_cleared ? (
        <div className="p-3 bg-pale-green/30 border border-brand-200 rounded-xl flex items-center space-x-2 text-forest text-xs font-semibold">
          <CheckCircle2 className="w-4 h-4 text-forest shrink-0" />
          <span>All lifestyle dealbreakers cleared successfully.</span>
        </div>
      ) : (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl space-y-1.5 text-rose-800 text-xs">
          <div className="flex items-center space-x-1.5 font-bold text-rose-900">
            <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0" />
            <span>Lifestyle Conflict Detected</span>
          </div>
          {score.conflicts && score.conflicts.length > 0 ? (
            <ul className="list-disc list-inside text-rose-700 pl-1 space-y-0.5">
              {score.conflicts.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          ) : (
            <p>One or more hard dealbreaker constraints were not satisfied.</p>
          )}
        </div>
      )}

      {/* 10 Dimensions Accordion / List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between text-xs font-bold text-charcoal uppercase tracking-wider">
          <span>10-Dimension Breakdown</span>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-forest hover:underline flex items-center gap-1 font-semibold normal-case"
          >
            <span>{expanded ? "Collapse details" : "Expand all 10"}</span>
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        <div className="space-y-3">
          {dimensions.slice(0, expanded ? 10 : 5).map((dim) => {
            const barColor = getTierColor(dim.value);
            const tierLabel = getTierLabel(dim.value);

            return (
              <div key={dim.key} className="space-y-1 p-2.5 rounded-xl hover:bg-slate-50/70 transition-colors">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-charcoal">{dim.name}</span>
                  <div className="flex items-center space-x-2">
                    <span className="text-[11px] font-medium text-charcoal-muted">{tierLabel}</span>
                    <span className="font-bold text-charcoal w-8 text-right">{dim.value}%</span>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                    style={{ width: `${Math.min(100, Math.max(5, dim.value))}%` }}
                  />
                </div>

                {/* Explanation text */}
                <p className="text-[11px] text-charcoal-muted leading-tight pt-0.5">
                  {dim.explanation}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Scientific Matching Disclaimer */}
      <div className="pt-3 border-t border-slate-100 flex items-start space-x-2 text-[11px] text-charcoal-muted leading-relaxed">
        <Info className="w-4 h-4 text-forest shrink-0 mt-0.5" />
        <p>
          Calculated by {score.algorithm_version || "Flatmate Engine v1.0"}. Compatibility scores represent
          lifestyle alignment based on questionnaire responses; they do not guarantee personal harmony. We recommend
          chatting and meeting in person before committing to a lease.
        </p>
      </div>
    </div>
  );
};
