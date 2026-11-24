import React from "react";
import Link from "next/link";
import { Card, Badge, Button } from "@flatmate/ui";
import { ShieldAlert, AlertTriangle, CheckCircle2, Lock, EyeOff, MessageSquare } from "lucide-react";

export const metadata = {
  title: "Safety & Scam Prevention Guidelines | Flatmate",
  description: "Learn how Flatmate protects renters, flatmates, and owners against fraud and privacy violations.",
};

export default function SafetyPage() {
  return (
    <div className="max-w-4xl mx-auto py-12 px-4 sm:px-6 space-y-8">
      {/* Header */}
      <div className="space-y-3">
        <Badge variant="warning" size="md" className="inline-flex items-center space-x-1.5">
          <ShieldAlert className="w-4 h-4" />
          <span>Trust & Safety Protocols</span>
        </Badge>
        <h1 className="text-3xl font-extrabold text-charcoal">Safety & Scam Prevention Guidelines</h1>
        <p className="text-sm text-charcoal-muted leading-relaxed">
          Flatmate implements strict technological defenses to protect our community. Review these guidelines
          to protect your financial and personal safety during your housing search.
        </p>
      </div>

      {/* Critical Scam Warnings */}
      <Card className="p-6 border-amber-200 bg-amber-50/50 space-y-4">
        <div className="flex items-center space-x-2.5 text-amber-900 font-bold text-base">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
          <span>Golden Rule: Never Pay Advance &quot;Token Money&quot; Before Physical Viewing</span>
        </div>
        <p className="text-sm text-amber-800 leading-relaxed">
          Fraudulent actors commonly pose as NRI owners, military officers, or gatekeepers requesting ₹2,000 to ₹10,000
          via UPI or bank transfer to &quot;issue a gate pass&quot; or &quot;hold the room&quot; before you inspect the flat.
          <strong> Flatmate never requires advance token payments for property viewings.</strong>
        </p>
      </Card>

      {/* Security Features */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="p-6 space-y-3">
          <div className="w-10 h-10 rounded-xl bg-forest/10 text-forest flex items-center justify-center">
            <EyeOff className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-charcoal">Location Privacy (DPDP Act)</h3>
          <p className="text-xs text-charcoal-muted leading-relaxed">
            Exact apartment numbers, door numbers, and building coordinates are obscured from public searches.
            Exact details are only revealed once an in-person viewing appointment is mutually confirmed.
          </p>
        </Card>

        <Card className="p-6 space-y-3">
          <div className="w-10 h-10 rounded-xl bg-forest/10 text-forest flex items-center justify-center">
            <Lock className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-charcoal">Phone Number Protection</h3>
          <p className="text-xs text-charcoal-muted leading-relaxed">
            Your phone number is masked by default on all profiles and listings unless you explicitly toggle public display
            in your Privacy Settings.
          </p>
        </Card>

        <Card className="p-6 space-y-3">
          <div className="w-10 h-10 rounded-xl bg-forest/10 text-forest flex items-center justify-center">
            <MessageSquare className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-charcoal">In-App Scam Detection</h3>
          <p className="text-xs text-charcoal-muted leading-relaxed">
            Our messaging system detects suspicious token payment phrasing and unauthorized off-platform payment demands,
            surfacing instant warnings in the chat thread.
          </p>
        </Card>

        <Card className="p-6 space-y-3">
          <div className="w-10 h-10 rounded-xl bg-forest/10 text-forest flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-charcoal">Verified mobile and email</h3>
          <p className="text-xs text-charcoal-muted leading-relaxed">
            A verified badge means the member confirmed their mobile number or a work or college email with a
            one-time code. It is not an ID check, so always use good judgment when meeting prospective roommates.
          </p>
        </Card>
      </div>

      {/* Reporting action */}
      <Card className="p-6 bg-slate-50 border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h4 className="text-sm font-bold text-charcoal">Encountered suspicious activity?</h4>
          <p className="text-xs text-charcoal-muted mt-0.5">
            Use the &quot;Report&quot; button on any listing, profile, or message thread to escalate to human moderation.
          </p>
        </div>
        <Link href="/help">
          <Button variant="outline" size="sm" className="shrink-0">
            Visit Help Center
          </Button>
        </Link>
      </Card>
    </div>
  );
}
