import React from 'react';
import { AlertCircle, ShieldAlert } from 'lucide-react';

export interface DealbreakerAlertProps {
  conflicts: string[];
  cappedScore?: number;
}

export const DealbreakerAlert: React.FC<DealbreakerAlertProps> = ({
  conflicts,
  cappedScore = 30.0,
}) => {
  if (!conflicts || conflicts.length === 0) return null;

  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50/70 p-4 shadow-sm text-rose-900 space-y-2">
      <div className="flex items-center space-x-2">
        <ShieldAlert className="h-5 w-5 text-rose-600 flex-shrink-0" />
        <h4 className="font-semibold text-sm">Dealbreaker Policy Enforced</h4>
      </div>
      <p className="text-xs text-rose-700">
        The compatibility engine capped the overall compatibility at{' '}
        <span className="font-bold underline">{cappedScore}%</span> due to strict non-negotiable household rules:
      </p>
      <ul className="space-y-1 text-xs text-rose-800 list-disc list-inside">
        {conflicts.map((conflict, idx) => (
          <li key={idx} className="flex items-start space-x-1.5">
            <AlertCircle className="h-3.5 w-3.5 text-rose-500 inline mt-0.5 flex-shrink-0" />
            <span>{conflict}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};
