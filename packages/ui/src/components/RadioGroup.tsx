import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface RadioOption {
  value: string;
  label: React.ReactNode;
  description?: React.ReactNode;
  disabled?: boolean;
}

export interface RadioGroupProps {
  name: string;
  value?: string;
  onChange?: (value: string) => void;
  options: RadioOption[];
  label?: string;
  error?: string;
  className?: string;
  orientation?: 'horizontal' | 'vertical';
}

export const RadioGroup: React.FC<RadioGroupProps> = ({
  name,
  value,
  onChange,
  options,
  label,
  error,
  className,
  orientation = 'vertical',
}) => {
  return (
    <fieldset className={twMerge('w-full', className)}>
      {label && <legend className="block text-sm font-medium text-charcoal mb-2">{label}</legend>}
      <div
        className={clsx(
          'flex gap-3',
          orientation === 'vertical' ? 'flex-col' : 'flex-row flex-wrap'
        )}
      >
        {options.map((option) => {
          const optionId = `${name}-${option.value}`;
          const isChecked = value === option.value;

          return (
            <label
              key={option.value}
              htmlFor={optionId}
              className={clsx(
                'flex items-start space-x-3 p-3 rounded-xl border transition-all cursor-pointer select-none',
                isChecked
                  ? 'border-brand-500 bg-brand-50/50 ring-1 ring-brand-500'
                  : 'border-slate-200 bg-white hover:border-slate-300',
                option.disabled && 'opacity-50 cursor-not-allowed'
              )}
            >
              <input
                type="radio"
                id={optionId}
                name={name}
                value={option.value}
                checked={isChecked}
                disabled={option.disabled}
                onChange={() => onChange?.(option.value)}
                className="mt-0.5 w-4 h-4 text-forest border-slate-300 focus:ring-brand-500 focus:ring-2 cursor-pointer"
              />
              <div className="text-sm">
                <span className="font-medium text-charcoal block">{option.label}</span>
                {option.description && (
                  <span className="text-xs text-slate-500 mt-0.5 block">{option.description}</span>
                )}
              </div>
            </label>
          );
        })}
      </div>
      {error && <p className="mt-1.5 text-xs text-rose-600 font-medium" role="alert">{error}</p>}
    </fieldset>
  );
};
