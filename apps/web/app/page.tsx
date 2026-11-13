import React from "react";
import Link from "next/link";
import { SearchBar } from "@/components/SearchBar";
import { PropertyCard } from "@/components/PropertyCard";
import { FlatmateCard } from "@/components/FlatmateCard";
import { Button } from "@flatmate/ui";
import { Sparkles, ShieldCheck, MapPin, Users, ArrowRight, HeartHandshake, CheckCircle } from "lucide-react";

// Mock initial data for landing page rendering
const FEATURED_PROPERTIES = [
  {
    id: "b1111111-1111-1111-1111-111111111111",
    owner_id: "55555555-5555-5555-5555-555555555555",
    title: "Sun-Drenched 3BR Flat in Mission Dolores with Roof Deck",
    description: "Gorgeous Victorian flat with hardwood floors, chef kitchen, and panoramic roof deck.",
    property_type: "apartment" as const,
    latitude: 37.7601,
    longitude: -122.4269,
    address: "482 Valencia St",
    city: "San Francisco",
    state: "CA",
    postal_code: "94103",
    country: "USA",
    monthly_rent: 4200,
    deposit: 4200,
    bills_included: false,
    total_bedrooms: 3,
    total_bathrooms: 2,
    available_from: "2026-12-01",
    is_furnished: true,
    pets_allowed: true,
    smoking_allowed: false,
    images: ["https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800"],
    amenities: ["in_unit_laundry", "roof_deck", "dishwasher"],
    rooms: [],
    is_active: true,
    created_at: "2026-11-01T00:00:00Z",
  },
  {
    id: "b2222222-2222-2222-2222-222222222222",
    owner_id: "66666666-6666-6666-6666-666666666666",
    title: "Modern Hayes Valley Loft with Private Balcony",
    description: "Ultra-modern designer loft unit featuring floor-to-ceiling windows and high speed fiber.",
    property_type: "condo" as const,
    latitude: 37.7758,
    longitude: -122.4243,
    address: "315 Octavia St",
    city: "San Francisco",
    state: "CA",
    postal_code: "94102",
    country: "USA",
    monthly_rent: 3400,
    deposit: 3400,
    bills_included: true,
    total_bedrooms: 2,
    total_bathrooms: 2,
    available_from: "2026-11-25",
    is_furnished: true,
    pets_allowed: false,
    smoking_allowed: false,
    images: ["https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800"],
    amenities: ["central_ac", "elevator", "bike_storage"],
    rooms: [],
    is_active: true,
    created_at: "2026-11-02T00:00:00Z",
  },
];

const FEATURED_FLATMATES = [
  {
    id: "a1111111-1111-1111-1111-111111111111",
    user_id: "11111111-1111-1111-1111-111111111111",
    display_name: "Priya S.",
    avatar_url: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=400",
    bio: "Software engineer working in tech. Early riser, tidy, vegan, loves trail running.",
    occupation: "Software Engineer",
    budget_min: 1200,
    budget_max: 1800,
    move_in_date: "2026-12-01",
    lifestyle_traits: {
      sleep_schedule: "early_bird" as const,
      cleanliness_level: 5 as const,
      social_battery: "moderate" as const,
      work_arrangement: "hybrid" as const,
      diet: "vegan" as const,
      smoking: "never" as const,
      pets: "cats_ok" as const,
      guests_policy: "occasional_weekends",
    },
    preferred_locations: ["Downtown", "Mission District"],
    created_at: "2026-11-01T00:00:00Z",
    updated_at: "2026-11-01T00:00:00Z",
  },
  {
    id: "a2222222-2222-2222-2222-222222222222",
    user_id: "22222222-2222-2222-2222-222222222222",
    display_name: "Marcus V.",
    avatar_url: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400",
    bio: "Product designer & coffee lover. Very respectful of quiet hours, loves cooking Saturday dinners.",
    occupation: "Senior Product Designer",
    budget_min: 1400,
    budget_max: 2100,
    move_in_date: "2026-11-20",
    lifestyle_traits: {
      sleep_schedule: "early_bird" as const,
      cleanliness_level: 4 as const,
      social_battery: "extroverted" as const,
      work_arrangement: "hybrid" as const,
      diet: "omnivore" as const,
      smoking: "never" as const,
      pets: "loves_pets" as const,
      guests_policy: "weekends_welcome",
    },
    preferred_locations: ["Mission District", "SoMa"],
    created_at: "2026-11-01T00:00:00Z",
    updated_at: "2026-11-01T00:00:00Z",
  },
];

export default function HomePage() {
  return (
    <div className="space-y-20 pb-20">
      {/* 1. Hero Section */}
      <section className="relative pt-12 pb-24 md:pt-20 md:pb-32 overflow-hidden bg-gradient-to-b from-indigo-50/50 via-white to-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          <div className="inline-flex items-center space-x-2 bg-indigo-100/80 border border-indigo-200/80 text-indigo-700 text-xs font-semibold px-4 py-1.5 rounded-full mb-6 shadow-2xs">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI & Vector-Powered Lifestyle Roommate Matching</span>
          </div>

          <h1 className="text-4xl sm:text-6xl font-extrabold text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight">
            Stop guessing. Live with someone who{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
              actually fits your life.
            </span>
          </h1>

          <p className="mt-6 text-lg sm:text-xl text-slate-600 max-w-2xl mx-auto leading-relaxed">
            We match your sleep schedule, cleanliness standards, budget, and habits with verified flatmates and top-tier co-living rentals.
          </p>

          <div className="mt-10">
            <SearchBar />
          </div>

          {/* Social Proof Stats */}
          <div className="mt-12 grid grid-cols-2 sm:grid-cols-4 gap-4 max-w-3xl mx-auto pt-8 border-t border-slate-200/60">
            <div>
              <div className="text-2xl font-bold text-slate-900">94%</div>
              <div className="text-xs text-slate-500 font-medium">Match Accuracy</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-900">12k+</div>
              <div className="text-xs text-slate-500 font-medium">Verified Seekers</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-900">&lt; 14 Days</div>
              <div className="text-xs text-slate-500 font-medium">Avg. Time to Move In</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-slate-900">0 Fraud</div>
              <div className="text-xs text-slate-500 font-medium">Guaranteed Safety</div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. How It Works Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-3xl font-extrabold text-slate-900">How Flatmate Platform Works</h2>
          <p className="text-slate-600 mt-3 text-base">
            Three simple steps to secure your dream space and compatible roommate.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="bg-white p-8 rounded-2xl border border-slate-200/80 shadow-xs relative">
            <div className="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-lg mb-6">
              1
            </div>
            <h3 className="font-bold text-slate-900 text-lg mb-2">Take the Lifestyle Quiz</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Tell us your quiet hours, cleaning habits, remote work rhythm, and budget. Our engine compiles your 64-D compatibility vector.
            </p>
          </div>

          <div className="bg-white p-8 rounded-2xl border border-slate-200/80 shadow-xs relative">
            <div className="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold text-lg mb-6">
              2
            </div>
            <h3 className="font-bold text-slate-900 text-lg mb-2">Connect & Team-Up</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Explore high-compatibility matches with transparent alignment radar charts. Chat in real-time or form a hunting syndicate.
            </p>
          </div>

          <div className="bg-white p-8 rounded-2xl border border-slate-200/80 shadow-xs relative">
            <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-lg mb-6">
              3
            </div>
            <h3 className="font-bold text-slate-900 text-lg mb-2">Apply Jointly with Confidence</h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              Submit verified application dossiers directly to vetted property owners and sign leases with zero awkward surprises.
            </p>
          </div>
        </div>
      </section>

      {/* 3. Featured Rooms & Listings */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-end mb-8">
          <div>
            <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider">Curated Co-Living</span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">Available Rooms & Shared Flats</h2>
          </div>
          <Link href="/properties" className="text-sm font-semibold text-indigo-600 hover:text-indigo-700 flex items-center space-x-1">
            <span>View all listings</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {FEATURED_PROPERTIES.map((prop) => (
            <PropertyCard key={prop.id} property={prop} matchScore={96} />
          ))}
        </div>
      </section>

      {/* 4. Top Compatible Flatmates */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-end mb-8">
          <div>
            <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider">Seeker Directory</span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">Top Matching Roommates</h2>
          </div>
          <Link href="/flatmates" className="text-sm font-semibold text-indigo-600 hover:text-indigo-700 flex items-center space-x-1">
            <span>Browse all flatmates</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {FEATURED_FLATMATES.map((profile, i) => (
            <FlatmateCard key={profile.id} profile={profile as any} matchScore={i === 0 ? 98 : 91} />
          ))}
        </div>
      </section>

      {/* 5. Trust & Verification Banner */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-slate-900 rounded-3xl p-8 sm:p-12 text-white relative overflow-hidden flex flex-col md:flex-row items-center justify-between gap-8">
          <div className="space-y-4 max-w-xl">
            <div className="inline-flex items-center space-x-2 bg-emerald-500/20 text-emerald-300 text-xs font-semibold px-3 py-1 rounded-full border border-emerald-500/30">
              <ShieldCheck className="w-4 h-4" />
              <span>Verified Community</span>
            </div>
            <h3 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Safety, privacy, and genuine human respect.
            </h3>
            <p className="text-slate-300 text-sm leading-relaxed">
              Every applicant verifies their government identification, university enrollment, or corporate credentials before exchanging private contact details.
            </p>
          </div>
          <Link href="/register">
            <Button variant="primary" size="lg" className="bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg whitespace-nowrap">
              Join the Verified Network
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
