"use client";

import React from 'react';
import { ThumbsUp, ThumbsDown, MapPin, Users } from 'lucide-react';

export interface GroupWishlistCardProps {
  propertyId: string;
  title: string;
  locality: string;
  monthlyRent: number;
  votes: Record<string, string>; // userId -> 'up' | 'down' | 'neutral'
  currentUserId: string;
  onVote: (propertyId: string, vote: 'up' | 'down' | 'neutral') => Promise<void>;
}

export const GroupWishlistCard: React.FC<GroupWishlistCardProps> = ({
  propertyId,
  title,
  locality,
  monthlyRent,
  votes,
  currentUserId,
  onVote,
}) => {
  const upvotesCount = Object.values(votes).filter((v) => v === 'up').length;
  const downvotesCount = Object.values(votes).filter((v) => v === 'down').length;
  const myVote = votes[currentUserId];

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-4 hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start">
        <div>
          <h4 className="font-semibold text-gray-900 text-sm line-clamp-1">{title}</h4>
          <div className="flex items-center space-x-1 text-xs text-gray-500 mt-1">
            <MapPin className="w-3.5 h-3.5 text-gray-400" />
            <span>{locality}</span>
          </div>
        </div>
        <div className="text-right">
          <span className="font-bold text-indigo-600 text-sm">₹{monthlyRent.toLocaleString('en-IN')}</span>
          <span className="text-[10px] text-gray-400 block">/month</span>
        </div>
      </div>

      {/* Voting Bar */}
      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <div className="flex items-center space-x-2 text-xs text-gray-600">
          <Users className="w-4 h-4 text-gray-400" />
          <span>Group Consensus:</span>
          <span className="font-semibold text-emerald-600">+{upvotesCount}</span>
          <span className="font-semibold text-rose-500">-{downvotesCount}</span>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => onVote(propertyId, myVote === 'up' ? 'neutral' : 'up')}
            className={`p-2 rounded-lg border text-xs flex items-center space-x-1 transition-colors ${
              myVote === 'up'
                ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                : 'border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            <ThumbsUp className="w-3.5 h-3.5" />
            <span>Like</span>
          </button>

          <button
            onClick={() => onVote(propertyId, myVote === 'down' ? 'neutral' : 'down')}
            className={`p-2 rounded-lg border text-xs flex items-center space-x-1 transition-colors ${
              myVote === 'down'
                ? 'bg-rose-50 border-rose-300 text-rose-700'
                : 'border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            <ThumbsDown className="w-3.5 h-3.5" />
            <span>Pass</span>
          </button>
        </div>
      </div>
    </div>
  );
};
