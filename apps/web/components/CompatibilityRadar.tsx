"use client";

import React from "react";
import { ScoreBreakdown } from "@flatmate/contracts";
import { Sparkles, ShieldAlert, CheckCircle2 } from "lucide-react";

export interface CompatibilityRadarProps {
  score: ScoreBreakdown;
}

export const CompatibilityRadar: React.FC<CompatibilityRadarProps> = ({ score }) => {
  const categories = [
    { label: "Lifestyle & Vibe", value: score.lifestyle_score, color: "bg-indigo-500" },
    { label: "Cleanliness Match", value: score.cleanliness_alignment, color: "bg-emerald-500" },
    { label: "Schedule & Quiet Hours", value: score.schedule_alignment, color: "bg-amber-500" },
    { label: "Social Battery", value: score.social_alignment, color: "bg-purple-500" },
    { label: "Budget Overlap", value: score.budget_alignment, color: "bg-blue-500" },
  ];

  return (
    <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <div>
          <h4 className="font-bold text-slate-900 text-lg flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-600" />
            Compatibility Analysis
          </h4>
          <p className="text-xs text-slate-500 mt-0.5">
            Algorithmic vector and categorical lifestyle breakdown
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-extrabold text-indigo-600">
            {Math.round(score.overall_score)}%
          </div>
          <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
            Overall Fit
          </span>
        </div>
      </div>

      {/* Dealbreaker Alert */}
      {!score.dealbreakers_cleared && (
        <div className="mt-4 p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-2 text-rose-700 text-xs">
          <ShieldAlert className="w-4 h-4 shrink-0 text-rose-600" />
          <span>Potential lifestyle dealbreaker detected (smoking / pet allergies).</span>
        </div>
      )}

      {/* Axis Bars */}
      <div className="mt-5 space-y-3.5">
        {categories.map((cat) => (
          <div key={cat.label}>
            <div className="flex justify-between text-xs font-semibold mb-1">
              <span className="text-slate-700">{cat.label}</span>
              <span className="text-slate-500">{cat.value}%</span>
            </div>
            <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${cat.color}`}
                style={{ width: `${Math.min(100, Math.max(5, cat.value))}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Shared traits tags */}
      {score.shared_interests && score.shared_interests.length > 0 && (
        <div className="mt-5 pt-4 border-t border-slate-100">
          <span className="text-xs font-semibold text-slate-700 block mb-2">Common Habits:</span>
          <div className="flex flex-wrap gap-1.5">
            {score.shared_interests.map((trait, idx) => (
              <span
                key={idx}
                className="inline-flex items-center space-x-1 text-xs bg-slate-100 text-slate-700 px-2.5 py-1 rounded-lg"
              >
                <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                <span>{trait}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
