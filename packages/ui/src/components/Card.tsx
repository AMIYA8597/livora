import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className,
  hoverable = false,
  ...props
}) => {
  return (
    <div
      className={twMerge(
        clsx(
          'bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden',
          hoverable && 'transition-all duration-200 hover:shadow-md hover:border-gray-200',
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  );
};
