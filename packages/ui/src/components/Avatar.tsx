import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface AvatarProps {
  src?: string | null;
  alt: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  isVerified?: boolean;
  className?: string;
}

export const Avatar: React.FC<AvatarProps> = ({
  src,
  alt,
  size = 'md',
  isVerified = false,
  className,
}) => {
  const sizes = {
    sm: 'w-8 h-8 text-xs',
    md: 'w-10 h-10 text-sm',
    lg: 'w-14 h-14 text-base',
    xl: 'w-20 h-20 text-xl',
  };

  const initials = alt
    .split(' ')
    .map((n) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <div className={twMerge(clsx('relative inline-block select-none', className))}>
      {src ? (
        <img
          src={src}
          alt={alt}
          className={twMerge(clsx('rounded-full object-cover ring-2 ring-white', sizes[size]))}
        />
      ) : (
        <div
          className={twMerge(
            clsx(
              'rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center font-semibold ring-2 ring-white shadow-sm',
              sizes[size]
            )
          )}
        >
          {initials}
        </div>
      )}
      {isVerified && (
        <span
          className="absolute bottom-0 right-0 block rounded-full bg-emerald-500 ring-2 ring-white text-white p-0.5"
          title="Verified User"
        >
          <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </span>
      )}
    </div>
  );
};
