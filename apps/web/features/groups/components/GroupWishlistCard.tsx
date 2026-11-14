"use client";

import React, { useState } from "react";
import { ThumbsUp, ThumbsDown, MapPin, Users, Loader2, AlertCircle } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

export interface GroupWishlistCardProps {
  propertyId: string;
  title: string;
  locality: string;
  monthlyRent: number;
  votes: Record<string, string>; // userId -> 'up' | 'down' | 'neutral'
  currentUserId: string;
  isMember?: boolean;
  onVote: (propertyId: string, vote: "up" | "down" | "neutral") => Promise<void>;
}

export const GroupWishlistCard: React.FC<GroupWishlistCardProps> = ({
  propertyId,
  title,
  locality,
  monthlyRent,
  votes = {},
  currentUserId,
  isMember = true,
  onVote,
}) => {
  const [isVoting, setIsVoting] = useState(false);
  const [voteError, setVoteError] = useState<string | null>(null);

  const upvotesCount = Object.values(votes).filter((v) => v === "up").length;
  const downvotesCount = Object.values(votes).filter((v) => v === "down").length;
  const myVote = votes[currentUserId];

  const handleVoteAction = async (targetVote: "up" | "down") => {
    if (!isMember) {
      setVoteError("Only active group members can vote on wishlist listings.");
      return;
    }

    setVoteError(null);
    setIsVoting(true);

    try {
      const nextVote = myVote === targetVote ? "neutral" : targetVote;
      await onVote(propertyId, nextVote);
    } catch (err: any) {
      setVoteError(err.message || "Failed to submit vote. Please try again.");
    } finally {
      setIsVoting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-xs space-y-4 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start gap-4">
        <div>
          <h4 className="font-bold text-slate-900 text-sm line-clamp-1">{title}</h4>
          <div className="flex items-center space-x-1 text-xs text-slate-500 mt-1">
            <MapPin className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <span>{locality}</span>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <span className="font-extrabold text-indigo-600 text-sm">
            {formatCurrency(monthlyRent, "INR")}
          </span>
          <span className="text-[10px] text-slate-400 block">/month target</span>
        </div>
      </div>

      {voteError && (
        <div className="flex items-center space-x-1.5 p-2 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs">
          <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>{voteError}</span>
        </div>
      )}

      {/* Voting Bar */}
      <div className="flex items-center justify-between pt-3 border-t border-slate-100">
        <div className="flex items-center space-x-2 text-xs text-slate-600">
          <Users className="w-4 h-4 text-slate-400" />
          <span className="font-medium">Consensus:</span>
          <span className="font-bold text-emerald-600">+{upvotesCount}</span>
          <span className="font-bold text-rose-500">-{downvotesCount}</span>
        </div>

        <div className="flex items-center space-x-2">
          <button
            type="button"
            disabled={isVoting || !isMember}
            onClick={() => handleVoteAction("up")}
            className={`px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center space-x-1.5 transition-all ${
              myVote === "up"
                ? "bg-emerald-50 border-emerald-300 text-emerald-700 shadow-2xs"
                : "border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            }`}
          >
            {isVoting && myVote !== "up" ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <ThumbsUp className="w-3.5 h-3.5" />
            )}
            <span>Like</span>
          </button>

          <button
            type="button"
            disabled={isVoting || !isMember}
            onClick={() => handleVoteAction("down")}
            className={`px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center space-x-1.5 transition-all ${
              myVote === "down"
                ? "bg-rose-50 border-rose-300 text-rose-700 shadow-2xs"
                : "border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            }`}
          >
            {isVoting && myVote !== "down" ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <ThumbsDown className="w-3.5 h-3.5" />
            )}
            <span>Pass</span>
          </button>
        </div>
      </div>
    </div>
  );
};
