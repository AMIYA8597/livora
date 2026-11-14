import React from "react";
import Link from "next/link";
import { Card, Badge, Button } from "@flatmate/ui";
import { ShieldCheck, Scale, FileText } from "lucide-react";

export const metadata = {
  title: "Terms of Service | Flatmate",
  description: "Terms of service, user rights, fair housing obligations, and listing guidelines on Flatmate.",
};

export default function TermsPage() {
  return (
    <div className="max-w-4xl mx-auto py-12 px-4 sm:px-6 space-y-8">
      <div className="space-y-3">
        <Badge variant="brand" size="md" className="inline-flex items-center space-x-1.5">
          <Scale className="w-4 h-4" />
          <span>Platform Agreement</span>
        </Badge>
        <h1 className="text-3xl font-extrabold text-charcoal">Terms of Service</h1>
        <p className="text-xs text-charcoal-muted">Last revised: November 13, 2026 • Effective immediately</p>
      </div>

      <Card className="p-8 space-y-6 border-warm-200">
        <section className="space-y-2">
          <h2 className="text-lg font-bold text-charcoal">1. Acceptance of Terms</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            By registering, accessing, or using the Flatmate platform, you agree to enter into a legally binding contract
            subject to these Terms of Service, our Privacy Policy, and our Community Guidelines. If you do not agree, do not
            access our services.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-charcoal">2. Authenticity & Zero-Fraud Policy</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            All users must provide accurate and verifiable information. Property owners, operators, and existing tenants
            agree to list only genuine, physically available accommodation with transparent rent, deposit, and maintenance fees.
            The posting of fake listings, phantom units, deceptive photos, or unauthorized subletting is strictly prohibited
            and results in permanent account suspension and reporting to law enforcement.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-charcoal">3. Fair Housing & Anti-Discrimination Standards</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            Flatmate is committed to safe, inclusive urban living. Users agree not to post discriminatory listings based on
            caste, religion, sexual orientation, disability, or marital status. While gender-specific accommodations
            (e.g., female-only PG floors or flats) are supported for personal safety and privacy reasons, arbitrary discrimination
            will be reviewed and moderated.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-charcoal">4. In-App Communications & Token Money Warning</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            For user security, initial communication and viewing appointments should be conducted through Flatmate&apos;s
            secure messaging system. Flatmate explicitly warns all users never to transfer advance token money, visit fees,
            or holding deposits via UPI or bank transfer before physically inspecting the premises and verifying owner tenancy documents.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-charcoal">5. Dispute Resolution & Moderation</h2>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            Flatmate reserves the right to moderate, hide, or delete content and suspend accounts that violate our safety,
            privacy, or verification standards. Users may appeal moderation decisions through our Help Center.
          </p>
        </section>

        <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
          <span className="text-xs text-slate-500">Have questions about our terms?</span>
          <Link href="/help">
            <Button variant="outline" size="sm">
              Contact Support
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
