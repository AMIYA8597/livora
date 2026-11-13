"use client";

import React from "react";
import Link from "next/link";
import { ProfileDTO } from "@flatmate/contracts";
import { Card, Avatar, Badge } from "@flatmate/ui";
import { MatchScoreBadge } from "@flatmate/ui";
import { formatCurrency } from "@/lib/utils";
import { Briefcase, Moon, Sun, CheckCircle2, ShieldCheck } from "lucide-react";

export interface FlatmateCardProps {
  profile: ProfileDTO;
  matchScore?: number;
  isVerified?: boolean;
}

export const FlatmateCard: React.FC<FlatmateCardProps> = ({
  profile,
  matchScore,
  isVerified = true,
}) => {
  const traits = profile.lifestyle_traits || ({} as any);

  return (
    <Link href={`/flatmates/${profile.user_id}`} className="group block h-full">
      <Card hoverable className="h-full flex flex-col p-5 border border-slate-200/80 shadow-2xs">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <Avatar
              src={profile.avatar_url}
              alt={profile.display_name}
              size="lg"
              isVerified={isVerified}
            />
            <div>
              <div className="flex items-center space-x-1.5">
                <h3 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                  {profile.display_name}
                </h3>
                {isVerified && (
                  <span title="Verified Seeker">
                    <ShieldCheck className="w-4 h-4 text-emerald-500" />
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 flex items-center space-x-1 mt-0.5">
                <Briefcase className="w-3 h-3 text-slate-400" />
                <span>{profile.occupation || "Young Professional"}</span>
              </p>
            </div>
          </div>
          {matchScore !== undefined && (
            <MatchScoreBadge score={matchScore} size="md" />
          )}
        </div>

        {/* Bio */}
        <p className="mt-3 text-xs text-slate-600 line-clamp-2 leading-relaxed flex-1">
          {profile.bio || "Looking for a clean, quiet, and friendly shared living space."}
        </p>

        {/* Lifestyle Highlights */}
        <div className="mt-4 flex flex-wrap gap-1.5">
          {traits.sleep_schedule === "early_bird" && (
            <Badge variant="info" size="sm" className="gap-1">
              <Sun className="w-3 h-3" /> Early Bird
            </Badge>
          )}
          {traits.sleep_schedule === "night_owl" && (
            <Badge variant="default" size="sm" className="gap-1">
              <Moon className="w-3 h-3" /> Night Owl
            </Badge>
          )}
          {traits.cleanliness_level && (
            <Badge variant="success" size="sm">
              Cleanliness {traits.cleanliness_level}/5
            </Badge>
          )}
          {traits.diet && (
            <Badge variant="warning" size="sm" className="capitalize">
              {traits.diet}
            </Badge>
          )}
        </div>

        {/* Budget Footer */}
        <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
          <span className="text-slate-500">Budget:</span>
          <span className="font-semibold text-slate-900">
            {formatCurrency(profile.budget_min)} - {formatCurrency(profile.budget_max)}/mo
          </span>
        </div>
      </Card>
    </Link>
  );
};
