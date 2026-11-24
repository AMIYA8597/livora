"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useApiQuery } from "@/hooks/useApiQuery";
import Link from "next/link";
import { SearchBar } from "@/components/SearchBar";
import { PropertyCard } from "@/components/PropertyCard";
import { FlatmateCard } from "@/components/FlatmateCard";
import { Button, Card, Badge, Skeleton, EmptyState } from "@flatmate/ui";
import { PropertyDTO } from "@flatmate/contracts";
import { useAuth } from "@/hooks/useAuth";
import {
  Sparkles,
  ShieldCheck,
  MapPin,
  Users,
  ArrowRight,
  HeartHandshake,
  CheckCircle,
  Home,
  Sliders,
  CalendarCheck,
  MessageSquare,
  Lock,
  HelpCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

export default function HomePage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const propertiesQuery = useApiQuery<PropertyDTO[]>("/properties", { limit: 6 });
  // The seeker directory is members-only.
  const flatmatesQuery = useApiQuery<any[]>(isAuthenticated ? "/flatmates/search" : null, { limit: 4 });
  const featuredProperties = propertiesQuery.data ?? [];
  const featuredFlatmates = flatmatesQuery.data ?? [];
  const loadingProps = propertiesQuery.isLoading;
  const loadingFlatmates = authLoading || flatmatesQuery.isLoading;
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const faqs = [
    {
      q: "How does Flatmate verify property listings?",
      a: "Every listing on Flatmate represents a real database inventory record with physical units, rooms, and beds. Listings with a Verified badge have been reviewed by our team. Members can verify their mobile number and a work or college email, and the badge on their profile shows it.",
    },
    {
      q: "How does the 10-dimension compatibility score work?",
      a: "Our algorithm calculates vector alignment across Cleanliness, Sleep schedules, Work routines, Diet preferences, Smoking, Drinking, Social rhythm, Guests, Budget, and Locality. Dealbreakers are checked strictly. Individual raw questionnaire answers are never shown to other users.",
    },
    {
      q: "How do viewing appointments and applications work?",
      a: "Seekers can book physical viewing visits directly through the property calendar in Indian Standard Time (IST). Applications can be submitted with proposed rent and move-in dates, allowing owners to review dossiers and approve visits before revealing exact door numbers.",
    },
    {
      q: "How does Flatmate protect my personal privacy and contact info?",
      a: "In compliance with India's DPDP Act 2023, exact residential coordinates and building numbers are obscured until a viewing is confirmed. Phone numbers are masked by default, and initial conversations are kept safely on-platform with automatic scam warnings.",
    },
    {
      q: "What should I do if someone asks for token money before a visit?",
      a: "Never transfer advance token money, gate pass fees, or holding deposits via UPI or bank transfer before physically inspecting the property. Flatmate will never ask you to pay before an in-person viewing. You can report suspicious users immediately.",
    },
  ];

  return (
    <div className="space-y-20 pb-20">
      {/* 1. Hero Section */}
      <section className="relative pt-12 pb-20 md:pt-20 md:pb-28 overflow-hidden bg-gradient-to-b from-warm-100/80 via-warm-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          <div className="inline-flex items-center space-x-2 bg-pale-green/60 border border-brand-200 text-forest text-xs font-semibold px-4 py-1.5 rounded-full mb-6 shadow-xs">
            <Sparkles className="w-3.5 h-3.5 text-secondary-green" />
            <span>Find your place. Find your people. Live better together.</span>
          </div>

          <h1 className="text-4xl sm:text-6xl font-extrabold text-charcoal tracking-tight max-w-4xl mx-auto leading-tight">
            Stop guessing. Live with someone who{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-forest to-secondary-green">
              actually fits your life.
            </span>
          </h1>

          <p className="mt-6 text-base sm:text-lg text-charcoal-muted max-w-2xl mx-auto leading-relaxed">
            Match lifestyle preferences, quiet hours, cleanliness, and budget with verified flatmates and
            vetted shared rentals in Bengaluru, Mumbai, Delhi NCR, Hyderabad, and Pune.
          </p>

          {/* Search Bar */}
          <div className="mt-10">
            <SearchBar />
          </div>

          {/* Quick Dual Actions */}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link href="/properties">
              <Button variant="outline" size="sm" className="font-semibold text-charcoal">
                Explore Available Accommodations →
              </Button>
            </Link>
            <Link href="/flatmates">
              <Button variant="ghost" size="sm" className="font-semibold text-forest">
                Find Compatible Flatmates →
              </Button>
            </Link>
          </div>

          {/* Core Trust Metrics */}
          <div className="mt-12 grid grid-cols-2 sm:grid-cols-4 gap-4 max-w-3xl mx-auto pt-8 border-t border-warm-200">
            <div>
              <div className="text-2xl font-bold text-forest">10-D</div>
              <div className="text-xs text-charcoal-muted font-medium">Lifestyle Dimensions</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-forest">100%</div>
              <div className="text-xs text-charcoal-muted font-medium">Verified ID Badges</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-forest">DPDP 2023</div>
              <div className="text-xs text-charcoal-muted font-medium">Location Privacy Fuzzing</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-forest">Zero Fake</div>
              <div className="text-xs text-charcoal-muted font-medium">Persisted Inventory Policy</div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. How It Works Section (5 Clear Steps) */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-14">
          <Badge variant="brand" size="md">
            Simple 5-Step Process
          </Badge>
          <h2 className="text-3xl font-extrabold text-charcoal mt-2">How Flatmate Works</h2>
          <p className="text-charcoal-muted mt-2 text-sm sm:text-base">
            From lifestyle discovery to moving in with peace of mind.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
          <div className="bg-white p-6 rounded-2xl border border-warm-200 shadow-xs relative flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-xl bg-pale-green/40 text-forest flex items-center justify-center font-bold text-sm mb-4">
                1
              </div>
              <h3 className="font-bold text-charcoal text-base mb-1">Create Profile</h3>
              <p className="text-xs text-charcoal-muted leading-relaxed">
                Add your budget and preferred localities, and verify your mobile and work or college email.
              </p>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-warm-200 shadow-xs relative flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-xl bg-pale-green/40 text-forest flex items-center justify-center font-bold text-sm mb-4">
                2
              </div>
              <h3 className="font-bold text-charcoal text-base mb-1">Lifestyle Preferences</h3>
              <p className="text-xs text-charcoal-muted leading-relaxed">
                Answer 10 behavioral lifestyle dimensions and establish strict dealbreakers.
              </p>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-warm-200 shadow-xs relative flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-xl bg-pale-green/40 text-forest flex items-center justify-center font-bold text-sm mb-4">
                3
              </div>
              <h3 className="font-bold text-charcoal text-base mb-1">Discover People</h3>
              <p className="text-xs text-charcoal-muted leading-relaxed">
                Browse compatible seekers with transparent alignment radar charts.
              </p>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-warm-200 shadow-xs relative flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-xl bg-pale-green/40 text-forest flex items-center justify-center font-bold text-sm mb-4">
                4
              </div>
              <h3 className="font-bold text-charcoal text-base mb-1">Find Accommodation</h3>
              <p className="text-xs text-charcoal-muted leading-relaxed">
                Explore real units, private rooms, and PG beds with transparent financials.
              </p>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-warm-200 shadow-xs relative flex flex-col justify-between">
            <div>
              <div className="w-10 h-10 rounded-xl bg-pale-green/40 text-forest flex items-center justify-center font-bold text-sm mb-4">
                5
              </div>
              <h3 className="font-bold text-charcoal text-base mb-1">Connect & Visit</h3>
              <p className="text-xs text-charcoal-muted leading-relaxed">
                Chat securely on-platform, submit applications, and book in-person viewings.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Real Accommodation Discovery Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-end mb-8">
          <div>
            <span className="text-xs font-bold text-secondary-green uppercase tracking-wider">
              Verified Properties
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-charcoal mt-1">
              Available Rooms & Shared Flats
            </h2>
          </div>
          <Link
            href="/properties"
            className="text-sm font-semibold text-secondary-green hover:text-forest flex items-center space-x-1"
          >
            <span>Explore all homes</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {loadingProps ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Skeleton variant="card" />
            <Skeleton variant="card" />
            <Skeleton variant="card" />
          </div>
        ) : featuredProperties.length === 0 ? (
          <EmptyState
            icon={MapPin}
            title="No active property listings found"
            description="Be the first verified landlord or tenant to list an accommodation on Flatmate."
            actionLabel="List a Property"
            onAction={() => router.push("/owner")}
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {featuredProperties.map((prop) => (
              <PropertyCard key={prop.id} property={prop} />
            ))}
          </div>
        )}
      </section>

      {/* 4. Flatmate Discovery & Lifestyle Compatibility */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-end mb-8">
          <div>
            <span className="text-xs font-bold text-secondary-green uppercase tracking-wider">
              Seeker Directory
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-charcoal mt-1">
              Compatible Roommates
            </h2>
          </div>
          <Link
            href="/flatmates"
            className="text-sm font-semibold text-secondary-green hover:text-forest flex items-center space-x-1"
          >
            <span>Browse seeker directory</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {loadingFlatmates ? (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <Skeleton variant="card" height={220} />
            <Skeleton variant="card" height={220} />
            <Skeleton variant="card" height={220} />
            <Skeleton variant="card" height={220} />
          </div>
        ) : !isAuthenticated ? (
          <Card className="p-10 text-center max-w-xl mx-auto border-warm-200 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-pale-green/40 text-forest flex items-center justify-center mx-auto">
              <Lock className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-charcoal">Privacy-Protected Seeker Directory</h3>
            <p className="text-sm text-charcoal-muted leading-relaxed">
              In accordance with our digital privacy policy, verified flatmate profiles and compatibility
              breakdowns are accessible only to authenticated members.
            </p>
            <div className="pt-2 flex justify-center gap-3">
              <Link href="/login">
                <Button variant="primary" size="md">
                  Sign In to Connect
                </Button>
              </Link>
              <Link href="/register">
                <Button variant="outline" size="md">
                  Create Account
                </Button>
              </Link>
            </div>
          </Card>
        ) : featuredFlatmates.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No flatmate profiles found nearby"
            description="Broaden your search or update your preferred localities in your profile settings."
            actionLabel="Update Profile"
            onAction={() => router.push("/profile")}
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {featuredFlatmates.map((profile) => (
              <FlatmateCard
                key={profile.id || profile.user_id}
                profile={profile}
                isVerified={profile.is_verified}
              />
            ))}
          </div>
        )}
      </section>

      {/* 5. Trust, Verification & Safety Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-forest rounded-3xl p-8 sm:p-12 text-white relative overflow-hidden flex flex-col md:flex-row items-center justify-between gap-8 shadow-xl">
          <div className="space-y-4 max-w-2xl">
            <div className="inline-flex items-center space-x-2 bg-pale-green/20 text-pale-green text-xs font-semibold px-3 py-1 rounded-full border border-pale-green/30">
              <ShieldCheck className="w-4 h-4 text-pale-green" />
              <span>Trust & Safety Architecture</span>
            </div>
            <h3 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Genuine security built into every step.
            </h3>
            <p className="text-warm-100 text-sm leading-relaxed">
              Verified mobile numbers and work or college emails, fuzzed locations until you choose to share, and
              real-time warnings about advance-payment scams in chats.
            </p>
            <p className="text-xs text-pale-green/80 italic">
              * Note: A verified badge confirms a member&apos;s mobile number or work or college email, not their identity or ownership of a property. Always inspect accommodation in person before transferring funds.
            </p>
          </div>
          <div className="flex flex-col sm:flex-row gap-3">
            <Link href="/safety">
              <Button variant="secondary" size="lg" className="bg-white text-forest hover:bg-pale-green shadow-sm">
                Safety Guidelines
              </Button>
            </Link>
            <Link href="/register">
              <Button variant="outline" size="lg" className="border-white text-white hover:bg-white/10">
                Join Flatmate
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* 6. Frequently Asked Questions Section */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        <div className="text-center space-y-2">
          <Badge variant="brand" size="md">
            Got Questions?
          </Badge>
          <h2 className="text-3xl font-extrabold text-charcoal">Frequently Asked Questions</h2>
          <p className="text-sm text-charcoal-muted">
            Clear, transparent answers on how our platform safeguards your housing search.
          </p>
        </div>

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
      </section>
    </div>
  );
}
