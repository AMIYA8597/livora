import React from 'react';

export interface FactorScore {
  score: number;
  explanation: string;
}

export interface CompatibilityBreakdownProps {
  overallScore: number;
  dealbreakersCleared: boolean;
  conflicts: string[];
  factors: Record<string, number>;
  explanations: Record<string, string>;
  algorithmVersion?: string;
}

const DIMENSION_LABELS: Record<string, string> = {
  working_schedule: 'Working Schedule (15%)',
  sleep_schedule: 'Sleep Schedule (15%)',
  budget: 'Budget Alignment (15%)',
  cleanliness: 'Cleanliness & Chores (12%)',
  lifestyle: 'Lifestyle & Habits (12%)',
  noise_and_lighting: 'Noise & Lighting (10%)',
  guests_and_social: 'Guests & Social Policy (7%)',
  food_and_cooking: 'Food & Cooking (5%)',
  professional_domain: 'Professional Domain (5%)',
  location: 'Preferred Neighborhood (4%)',
};

export const CompatibilityBreakdown: React.FC<CompatibilityBreakdownProps> = ({
  overallScore,
  dealbreakersCleared,
  conflicts,
  factors,
  explanations,
  algorithmVersion = 'v1.0-india-heuristic',
}) => {
  const isHighMatch = overallScore >= 80;
  const isModerate = overallScore >= 60 && overallScore < 80;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-6">
      {/* Header with Score */}
      <div className="flex items-center justify-between border-b border-gray-100 pb-4">
        <div>
          <h3 className="text-lg font-bold text-gray-900">10-Dimension Compatibility</h3>
          <p className="text-xs text-gray-500">Explainable matching engine • {algorithmVersion}</p>
        </div>
        <div className="text-right">
          <div
            className={`text-3xl font-extrabold ${
              isHighMatch
                ? 'text-emerald-600'
                : isModerate
                ? 'text-amber-500'
                : 'text-rose-600'
            }`}
          >
            {overallScore.toFixed(1)}%
          </div>
          <span className="text-xs text-gray-400">Mutual Fit</span>
        </div>
      </div>

      {/* Dealbreaker Alert */}
      {!dealbreakersCleared && conflicts.length > 0 && (
        <div className="bg-rose-50 border border-rose-200 rounded-lg p-4 space-y-1">
          <div className="flex items-center space-x-2 text-rose-700 font-semibold text-sm">
            <span>⚠️ Strict Dealbreaker Conflict Detected</span>
          </div>
          <ul className="list-disc list-inside text-xs text-rose-600 space-y-0.5">
            {conflicts.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {/* 10 Dimension Progress Bars */}
      <div className="space-y-4">
        {Object.entries(DIMENSION_LABELS).map(([key, label]) => {
          const score = factors[key] ?? 50;
          const explanation = explanations[key] ?? '';

          return (
            <div key={key} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-gray-700">{label}</span>
                <span className="font-semibold text-gray-900">{score}%</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-2 rounded-full transition-all duration-300 ${
                    score >= 80
                      ? 'bg-emerald-500'
                      : score >= 60
                      ? 'bg-amber-400'
                      : 'bg-rose-500'
                  }`}
                  style={{ width: `${Math.max(5, Math.min(100, score))}%` }}
                />
              </div>
              {explanation && (
                <p className="text-[11px] text-gray-500 italic">{explanation}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
