import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './Button';

export interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  onPageChange,
  className,
}) => {
  if (totalPages <= 1) return null;

  const pages: (number | string)[] = [];
  const delta = 1;

  for (let i = 1; i <= totalPages; i++) {
    if (
      i === 1 ||
      i === totalPages ||
      (i >= currentPage - delta && i <= currentPage + delta)
    ) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== '...') {
      pages.push('...');
    }
  }

  return (
    <nav
      role="navigation"
      aria-label="Pagination Navigation"
      className={`flex items-center justify-center space-x-1.5 my-6 ${className || ''}`}
    >
      <Button
        variant="outline"
        size="sm"
        disabled={currentPage <= 1}
        onClick={() => onPageChange(currentPage - 1)}
        aria-label="Go to previous page"
        className="px-2.5 py-1.5"
      >
        <ChevronLeft className="w-4 h-4" />
      </Button>

      {pages.map((p, idx) => {
        if (typeof p === 'string') {
          return (
            <span key={`ellipsis-${idx}`} className="px-2 text-slate-400 text-sm">
              ...
            </span>
          );
        }

        const isCurrent = p === currentPage;
        return (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            aria-current={isCurrent ? 'page' : undefined}
            className={`w-8 h-8 rounded-lg text-xs font-semibold transition-all ${
              isCurrent
                ? 'bg-forest text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-100 hover:text-charcoal'
            }`}
          >
            {p}
          </button>
        );
      })}

      <Button
        variant="outline"
        size="sm"
        disabled={currentPage >= totalPages}
        onClick={() => onPageChange(currentPage + 1)}
        aria-label="Go to next page"
        className="px-2.5 py-1.5"
      >
        <ChevronRight className="w-4 h-4" />
      </Button>
    </nav>
  );
};
