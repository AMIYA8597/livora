import React from "react";
import type { PropertyDTO } from "@flatmate/contracts";
import { Button, Card } from "@flatmate/ui";
import { Calendar, MessageSquare, ShieldCheck } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

interface BookingCardProps {
  property: PropertyDTO;
  onApply: () => void;
  onSchedule: () => void;
  onMessage: () => void;
  isStartingChat?: boolean;
  /** Owners viewing their own listing don't get applicant actions. */
  isOwnListing?: boolean;
}

export function BookingCard({ property, onApply, onSchedule, onMessage, isStartingChat, isOwnListing }: BookingCardProps) {
  const currency = property.currency || "INR";
  return (
    <Card className="p-6 lg:sticky lg:top-24 border-warm-200 shadow-md space-y-6 bg-white">
      <div>
        <span className="text-xs text-charcoal-muted font-medium">Monthly rent</span>
        <div className="text-3xl font-extrabold text-charcoal">
          {formatCurrency(property.monthly_rent, currency)}
          <span className="text-sm font-normal text-charcoal-muted"> /month</span>
        </div>
        <p className="text-xs text-charcoal-muted mt-1">
          Security deposit: {formatCurrency(property.security_deposit ?? 0, currency)}
        </p>
      </div>

      {isOwnListing ? (
        <p className="text-xs text-charcoal-muted bg-warm p-3 rounded-xl">This is your listing. Manage it from your owner portal.</p>
      ) : (
        <div className="space-y-3">
          <Button variant="primary" size="lg" className="w-full justify-center min-h-[48px]" onClick={onApply}>
            Apply for this place
          </Button>
          <Button variant="outline" size="md" className="w-full gap-2 justify-center min-h-[44px]" onClick={onSchedule}>
            <Calendar className="w-4 h-4 text-forest" />
            <span>Book a viewing</span>
          </Button>
          <Button
            variant="ghost"
            size="md"
            className="w-full gap-2 text-forest justify-center min-h-[44px]"
            onClick={onMessage}
            isLoading={isStartingChat}
          >
            <MessageSquare className="w-4 h-4" />
            <span>Message the host</span>
          </Button>
        </div>
      )}

      <div className="pt-4 border-t border-slate-100 space-y-2 text-xs text-charcoal-muted">
        <div className="flex items-center gap-2 text-forest font-semibold">
          <ShieldCheck className="w-4 h-4" />
          <span>Protected by Flatmate</span>
        </div>
        <p className="leading-relaxed">
          Never pay a token amount before an in-person viewing. Keep all communication on Flatmate.
        </p>
      </div>
    </Card>
  );
}
