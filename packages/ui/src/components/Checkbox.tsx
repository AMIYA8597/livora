import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: React.ReactNode;
  description?: React.ReactNode;
  error?: string;
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, description, error, className, id, ...props }, ref) => {
    const generatedId = React.useId();
    const checkId = id || (label ? generatedId : undefined);

    return (
      <div className="flex items-start space-x-3">
        <div className="flex items-center h-5">
          <input
            ref={ref}
            id={checkId}
            type="checkbox"
            className={twMerge(
              clsx(
                'w-4 h-4 text-forest border-slate-300 rounded focus:ring-brand-500 focus:ring-2 cursor-pointer transition-colors',
                error && 'border-rose-400',
                className
              )
            )}
            {...props}
          />
        </div>
        <div className="text-sm">
          <label htmlFor={checkId} className="font-medium text-charcoal cursor-pointer select-none">
            {label}
          </label>
          {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
          {error && <p className="text-xs text-rose-600 font-medium mt-1" role="alert">{error}</p>}
        </div>
      </div>
    );
  }
);

Checkbox.displayName = 'Checkbox';
