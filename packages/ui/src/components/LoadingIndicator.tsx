import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface LoadingIndicatorProps {
  size?: 'sm' | 'md' | 'lg';
  text?: string;
  className?: string;
}

export const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({
  size = 'md',
  text,
  className,
}) => {
  const sizes = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-3',
    lg: 'w-12 h-12 border-4',
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className={twMerge('flex flex-col items-center justify-center p-4 space-y-3', className)}
    >
      <div
        className={clsx(
          'animate-spin rounded-full border-forest/20 border-t-forest',
          sizes[size]
        )}
      />
      {text && <span className="text-xs font-medium text-slate-500">{text}</span>}
      <span className="sr-only">Loading content...</span>
    </div>
  );
};
