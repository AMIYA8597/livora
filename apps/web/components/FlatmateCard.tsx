"use client";

import React from "react";
import Link from "next/link";
import { ProfileDTO } from "@flatmate/contracts";
import { Card, Avatar, Badge, MatchScoreBadge } from "@flatmate/ui";
import { formatCurrency } from "@/lib/utils";
import { DIET_OPTIONS, optionLabel } from "@/features/profile/lifestyle-options";
import { Briefcase, Moon, Sun, ShieldCheck, MapPin, Heart, X, ThumbsUp } from "lucide-react";

export interface FlatmateCardProps {
  profile: ProfileDTO;
  matchScore?: number;
  isVerified?: boolean;
  onLike?: (userId: string, e: React.MouseEvent) => void;
  onPass?: (userId: string, e: React.MouseEvent) => void;
}

export const FlatmateCard: React.FC<FlatmateCardProps> = ({
  profile,
  matchScore,
  isVerified = true,
  onLike,
  onPass,
}) => {
  const traits = (profile.lifestyle_traits || {}) as Record<string, any>;
  const localities = profile.preferred_locations || [];

  return (
    <Link href={`/flatmates/${profile.user_id}`} className="group block h-full">
      <Card hoverable className="h-full flex flex-col p-5 border border-warm-200 shadow-xs rounded-2xl bg-white justify-between">
        <div>
          {/* Header */}
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
                  <h3 className="font-bold text-charcoal group-hover:text-forest transition-colors">
                    {profile.display_name}
                  </h3>
                  {isVerified && (
                    <span title="Verified Seeker">
                      <ShieldCheck className="w-4 h-4 text-forest" />
                    </span>
                  )}
                </div>
                <p className="text-xs text-charcoal-muted flex items-center space-x-1 mt-0.5">
                  <Briefcase className="w-3 h-3 text-slate-400" />
                  <span>{profile.occupation || "Working Professional"}</span>
                </p>
              </div>
            </div>
            {matchScore !== undefined && (
              <MatchScoreBadge score={matchScore} size="md" />
            )}
          </div>

          {/* Localities Preference */}
          {localities.length > 0 && (
            <div className="flex items-center space-x-1 text-[11px] text-charcoal-muted mt-2.5">
              <MapPin className="w-3 h-3 text-forest shrink-0" />
              <span className="truncate">{localities.join(", ")}</span>
            </div>
          )}

          {/* Bio */}
          <p className="mt-2.5 text-xs text-charcoal-muted line-clamp-2 leading-relaxed">
            {profile.bio || "Looking for a clean, respectful, and friendly shared living space."}
          </p>

          {/* Lifestyle Highlights */}
          <div className="mt-3.5 flex flex-wrap gap-1.5">
            {traits.sleep_schedule === "early_bird" && (
              <Badge variant="brand" size="sm" className="gap-1">
                <Sun className="w-3 h-3 text-secondary-green" /> Early Bird
              </Badge>
            )}
            {traits.sleep_schedule === "night_owl" && (
              <Badge variant="default" size="sm" className="gap-1">
                <Moon className="w-3 h-3 text-slate-500" /> Night Owl
              </Badge>
            )}
            {traits.cleanliness_level && (
              <Badge variant="forest" size="sm">
                Clean {traits.cleanliness_level}/5
              </Badge>
            )}
            {traits.diet_preference && (
              <Badge variant="warm" size="sm">
                {optionLabel(DIET_OPTIONS, traits.diet_preference)}
              </Badge>
            )}
          </div>
        </div>

        {/* Footer with Budget & Interaction Actions */}
        <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
          <div>
            <span className="text-[10px] text-charcoal-muted uppercase tracking-wider block">
              Budget
            </span>
            <span className="font-bold text-charcoal">
              {formatCurrency(profile.budget_min)} - {formatCurrency(profile.budget_max)}
            </span>
          </div>

          {(onLike || onPass) && (
            <div className="flex items-center space-x-1.5">
              {onPass && (
                <button
                  type="button"
                  onClick={(e) => onPass(profile.user_id, e)}
                  title="Pass"
                  className="p-1.5 text-slate-400 hover:text-charcoal hover:bg-slate-100 rounded-lg transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
              {onLike && (
                <button
                  type="button"
                  onClick={(e) => onLike(profile.user_id, e)}
                  title="Like / Match"
                  className="p-1.5 text-forest hover:text-white hover:bg-forest rounded-lg transition-colors border border-brand-200"
                >
                  <ThumbsUp className="w-4 h-4" />
                </button>
              )}
            </div>
          )}
        </div>
      </Card>
    </Link>
  );
};
