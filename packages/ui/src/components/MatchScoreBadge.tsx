import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface MatchScoreBadgeProps {
  score: number; // 0 to 100
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

export const MatchScoreBadge: React.FC<MatchScoreBadgeProps> = ({
  score,
  size = 'md',
  showLabel = true,
  className,
}) => {
  const rounded = Math.round(score);

  // Determine styling tier
  const isHigh = rounded >= 80;
  const isMedium = rounded >= 60 && rounded < 80;

  const colorConfig = isHigh
    ? {
        bg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        ring: 'text-emerald-600',
        dot: 'bg-emerald-500',
      }
    : isMedium
    ? {
        bg: 'bg-amber-50 text-amber-700 border-amber-200',
        ring: 'text-amber-500',
        dot: 'bg-amber-500',
      }
    : {
        bg: 'bg-rose-50 text-rose-700 border-rose-200',
        ring: 'text-rose-500',
        dot: 'bg-rose-500',
      };

  const sizes = {
    sm: 'text-xs px-2 py-0.5 gap-1',
    md: 'text-xs font-semibold px-2.5 py-1 gap-1.5',
    lg: 'text-sm font-bold px-3 py-1.5 gap-2',
  };

  return (
    <span
      className={twMerge(
        clsx(
          'inline-flex items-center rounded-full border shadow-2xs font-semibold select-none backdrop-blur-xs',
          colorConfig.bg,
          sizes[size],
          className
        )
      )}
    >
      <span className={clsx('w-1.5 h-1.5 rounded-full animate-pulse', colorConfig.dot)} />
      <span>{rounded}%</span>
      {showLabel && <span className="font-normal opacity-80">Match</span>}
    </span>
  );
};
