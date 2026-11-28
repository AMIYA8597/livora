import React from "react";
import Link from "next/link";
import { Card, Badge, Button } from "@flatmate/ui";
import { Shield, EyeOff, Lock, UserCheck } from "lucide-react";

export const metadata = {
  title: "Privacy Notice | Flatmate (DPDP Act 2023 Compliant)",
  description: "Learn how Flatmate safeguards your personal data, lifestyle preferences, and location privacy.",
};

export default function PrivacyPage() {
  return (
    <div className="max-w-4xl mx-auto py-12 px-4 sm:px-6 space-y-8">
      <div className="space-y-3">
        <Badge variant="success" size="md" className="inline-flex items-center space-x-1.5">
          <Shield className="w-4 h-4" />
          <span>DPDP Act 2023 Compliance</span>
        </Badge>
        <h1 className="text-3xl font-extrabold text-charcoal">Digital Privacy & Data Protection Notice</h1>
        <p className="text-xs text-charcoal-muted">Last updated: November 28, 2026</p>
      </div>

      <Card className="p-8 space-y-6 border-warm-200">
        <section className="space-y-2">
          <h2 className="text-lg font-bold text-charcoal">1. Principles of Data Minimization & Consent</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            In compliance with India&apos;s Digital Personal Data Protection (DPDP) Act 2023, Flatmate processes personal data
            solely for providing matching and rental accommodation services. We request explicit consent before collecting
            lifestyle vectors and phone numbers. When you verify a work or college email we keep only its domain, not the address.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-charcoal">2. Exact Residential Location Protection</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            To prevent stalking and ensure tenant privacy, exact apartment numbers, flat numbers, and pinpoint coordinates
            are concealed on public property cards. Only normalized locality names (e.g., &quot;HSR Layout Sector 2, Bengaluru&quot;)
            and approximate radius circles are displayed. The precise address is revealed only after a viewing appointment is mutually confirmed.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-charcoal">3. Lifestyle Questionnaire & Raw Response Isolation</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            Your detailed answers to the 10-dimension questionnaire (cleanliness, sleep schedules, drinking, smoking, diet, etc.)
            are transformed into normalized vector metrics. Other seekers and landlords see only compatibility percentages,
            high-level alignment indicators, and mutual dealbreaker clearances. Raw individual quiz answers are never exposed.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-charcoal">4. Phone Number & Contact Privacy Controls</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            By default, phone numbers are masked across all user profiles and search listings. Seekers and owners communicate
            in-app. You can manage your contact visibility at any time in your Privacy Settings.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-charcoal">5. AI-Powered Search</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            To understand searches like &quot;quiet furnished room near the metro&quot;, listing text (title, locality, amenities
            and description) and the words you type into listing search are sent to our search provider, Voyage AI, which turns
            them into numbers that capture their meaning. Never your name, phone number, email or exact address. Your profile&apos;s
            &quot;about me&quot; text, occupation and lifestyle answers are not sent: flatmate search and matching run on our own servers.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-charcoal">6. Data Retention & Account Deletion Requests</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            You hold the right to request a copy of your personal data or request permanent deletion of your account.
            When an account is deleted, personal data and questionnaire vectors are purged within 30 days, except records
            required for regulatory compliance, fraud prevention, and financial audit logs under Indian law.
          </p>
        </section>

        <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
          <span className="text-xs text-slate-500">Need to exercise your data privacy rights?</span>
          <Link href="/profile">
            <Button variant="outline" size="sm">
              Manage Privacy Settings
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
