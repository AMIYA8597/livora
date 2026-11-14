import React from 'react';
import { twMerge } from 'tailwind-merge';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './Button';

export interface ErrorStateProps {
  title?: string;
  message?: string;
  correlationId?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Something went wrong',
  message = 'We encountered an error processing your request. Please try again or contact support.',
  correlationId,
  onRetry,
  className,
}) => {
  return (
    <div
      role="alert"
      className={twMerge(
        'flex flex-col items-center justify-center text-center p-8 sm:p-10 bg-rose-50/50 rounded-2xl border border-rose-200 shadow-sm max-w-lg mx-auto my-6',
        className
      )}
    >
      <div className="w-12 h-12 rounded-xl bg-rose-100 flex items-center justify-center text-rose-600 mb-3">
        <AlertTriangle className="w-6 h-6" />
      </div>
      <h3 className="text-base font-bold text-rose-950">{title}</h3>
      <p className="text-sm text-rose-800 mt-1 max-w-sm">{message}</p>
      {correlationId && (
        <p className="text-xs text-rose-500 mt-2 font-mono">
          Ref ID: {correlationId}
        </p>
      )}
      {onRetry && (
        <div className="mt-5">
          <Button variant="danger" size="sm" onClick={onRetry} className="inline-flex items-center space-x-1.5">
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Try Again</span>
          </Button>
        </div>
      )}
    </div>
  );
};
