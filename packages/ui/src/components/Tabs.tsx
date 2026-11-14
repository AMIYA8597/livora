"use client";

import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface TabItem {
  id: string;
  label: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  badge?: React.ReactNode;
  disabled?: boolean;
}

export interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  className?: string;
  variant?: 'underline' | 'pills' | 'segmented';
}

export const Tabs: React.FC<TabsProps> = ({
  tabs,
  activeTab,
  onChange,
  className,
  variant = 'underline',
}) => {
  return (
    <div
      role="tablist"
      aria-label="Content Tabs"
      className={twMerge(
        clsx(
          'flex items-center overflow-x-auto no-scrollbar',
          variant === 'underline' && 'border-b border-slate-200 space-x-6',
          variant === 'pills' && 'space-x-2',
          variant === 'segmented' && 'bg-slate-100 p-1 rounded-xl space-x-1',
          className
        )
      )}
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        const Icon = tab.icon;

        if (variant === 'segmented') {
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              aria-controls={`panel-${tab.id}`}
              disabled={tab.disabled}
              onClick={() => onChange(tab.id)}
              className={clsx(
                'flex-1 flex items-center justify-center space-x-2 py-2 px-3 text-xs font-semibold rounded-lg transition-all',
                isActive
                  ? 'bg-white text-charcoal shadow-sm'
                  : 'text-slate-600 hover:text-charcoal hover:bg-white/50',
                tab.disabled && 'opacity-40 cursor-not-allowed'
              )}
            >
              {Icon && <Icon className="w-4 h-4" />}
              <span>{tab.label}</span>
              {tab.badge && <span className="ml-1.5">{tab.badge}</span>}
            </button>
          );
        }

        if (variant === 'pills') {
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              aria-controls={`panel-${tab.id}`}
              disabled={tab.disabled}
              onClick={() => onChange(tab.id)}
              className={clsx(
                'flex items-center space-x-2 py-2 px-4 text-xs font-semibold rounded-xl transition-all',
                isActive
                  ? 'bg-forest text-white shadow-sm'
                  : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200',
                tab.disabled && 'opacity-40 cursor-not-allowed'
              )}
            >
              {Icon && <Icon className="w-4 h-4" />}
              <span>{tab.label}</span>
              {tab.badge && <span className="ml-1.5">{tab.badge}</span>}
            </button>
          );
        }

        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            aria-controls={`panel-${tab.id}`}
            disabled={tab.disabled}
            onClick={() => onChange(tab.id)}
            className={clsx(
              'flex items-center space-x-2 py-3 text-sm font-medium border-b-2 transition-all whitespace-nowrap',
              isActive
                ? 'border-forest text-forest font-semibold'
                : 'border-transparent text-slate-500 hover:text-charcoal hover:border-slate-300',
              tab.disabled && 'opacity-40 cursor-not-allowed'
            )}
          >
            {Icon && <Icon className="w-4 h-4" />}
            <span>{tab.label}</span>
            {tab.badge && <span className="ml-1.5">{tab.badge}</span>}
          </button>
        );
      })}
    </div>
  );
};
