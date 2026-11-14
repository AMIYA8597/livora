"use client";

import React, { useEffect } from 'react';
import { clsx } from 'clsx';
import { X } from 'lucide-react';

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  children: React.ReactNode;
  position?: 'right' | 'left' | 'bottom';
  className?: string;
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  children,
  position = 'right',
  className,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const positions = {
    right: 'inset-y-0 right-0 max-w-md w-full',
    left: 'inset-y-0 left-0 max-w-md w-full',
    bottom: 'inset-x-0 bottom-0 max-h-[85vh] w-full rounded-t-2xl',
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true">
      <div
        className="fixed inset-0 bg-charcoal/40 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="fixed inset-0 flex justify-end pointer-events-none">
        <aside
          className={clsx(
            'pointer-events-auto bg-white shadow-2xl flex flex-col z-10 transition-transform duration-300 ease-in-out',
            positions[position],
            className
          )}
        >
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
            {title && <h2 className="text-base font-bold text-charcoal">{title}</h2>}
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-charcoal hover:bg-slate-100 rounded-lg transition-colors ml-auto"
              aria-label="Close drawer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-6">{children}</div>
        </aside>
      </div>
    </div>
  );
};
