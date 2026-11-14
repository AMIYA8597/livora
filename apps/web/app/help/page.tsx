"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Card, Button, Badge } from "@flatmate/ui";
import { HelpCircle, ChevronDown, ChevronUp, Mail, MessageCircle } from "lucide-react";

export default function HelpPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  const faqs = [
    {
      q: "How does the 10-dimension compatibility score work?",
      a: "Our algorithm calculates behavioral alignment across 10 distinct lifestyle dimensions: Cleanliness, Sleep schedules, Work routines, Diet habits, Smoking, Drinking, Social rhythm, Guests, Budget, and Locality. Raw answers are never shared; only category alignment and dealbreaker checks are calculated.",
    },
    {
      q: "Are the property listings real and verified?",
      a: "Yes. All listings on Flatmate correspond to persisted database units, rooms, and beds created by real owners and verified tenants. Listings with a 'Verified' badge have undergone verification review.",
    },
    {
      q: "How do viewing appointments work?",
      a: "You can request a viewing directly from any property page by selecting an available date and time slot. The host receives the request and can confirm or decline. Upon confirmation, exact address directions are unlocked.",
    },
    {
      q: "Can I team up with others before finding a flat?",
      a: "Yes! Use the 'Team-Up Groups' feature to create a hunting syndicate with friends or compatible seekers. You can pool your combined budget, add properties to a shared wishlist, and vote collaboratively.",
    },
    {
      q: "How do I report fake profiles, harassment, or scam requests?",
      a: "Click the 'Report' button on any user profile, listing, or message thread. Our safety moderators review reports with highest priority and take actions including warning, content removal, or account suspension.",
    },
    {
      q: "What are the rules for listing properties and PG beds?",
      a: "Listings must accurately disclose monthly rent, security deposit, maintenance fees, furnishing status, and house rules. Discriminatory restrictions violating local tenancy laws are strictly prohibited.",
    },
  ];

  return (
    <div className="max-w-4xl mx-auto py-12 px-4 sm:px-6 space-y-10">
      <div className="text-center space-y-3">
        <Badge variant="brand" size="md">
          Support & Guidance
        </Badge>
        <h1 className="text-3xl font-extrabold text-charcoal">Frequently Asked Questions & Help Center</h1>
        <p className="text-sm text-charcoal-muted max-w-xl mx-auto">
          Everything you need to know about finding flats, matching with flatmates, scheduling visits, and platform safety.
        </p>
      </div>

      {/* Accordion FAQs */}
      <div className="space-y-3">
        {faqs.map((faq, idx) => {
          const isOpen = openFaq === idx;
          return (
            <Card key={idx} className="overflow-hidden border-warm-200">
              <button
                onClick={() => setOpenFaq(isOpen ? null : idx)}
                className="w-full text-left p-5 flex items-center justify-between font-semibold text-charcoal hover:bg-slate-50 transition-colors"
                aria-expanded={isOpen}
              >
                <span className="text-sm sm:text-base">{faq.q}</span>
                {isOpen ? (
                  <ChevronUp className="w-5 h-5 text-forest shrink-0 ml-4" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-slate-400 shrink-0 ml-4" />
                )}
              </button>
              {isOpen && (
                <div className="px-5 pb-5 pt-1 text-sm text-charcoal-muted leading-relaxed border-t border-slate-100 bg-slate-50/50">
                  {faq.a}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      {/* Contact Support */}
      <Card className="p-8 bg-warm-100/70 border-warm-200 text-center space-y-4">
        <h3 className="text-lg font-bold text-charcoal">Still have questions?</h3>
        <p className="text-sm text-charcoal-muted max-w-md mx-auto">
          Our customer support and trust & safety team is available to assist you with any questions or tenancy disputes.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <a
            href="mailto:support@flatmate.internal"
            className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-forest text-white text-sm font-semibold hover:bg-forest-dark transition-colors"
          >
            <Mail className="w-4 h-4" />
            <span>Email Support</span>
          </a>
          <Link href="/safety">
            <Button variant="outline" size="md">
              Review Safety Rules
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
