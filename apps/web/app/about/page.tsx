import React from "react";
import Link from "next/link";
import { Card, Button, Badge } from "@flatmate/ui";
import { Compass, Users, ShieldCheck, HeartHandshake, ArrowRight } from "lucide-react";

export const metadata = {
  title: "About Us | Flatmate Rental & Compatibility Platform",
  description: "Find your place. Find your people. Live better together.",
};

export default function AboutPage() {
  return (
    <div className="max-w-5xl mx-auto py-12 px-4 sm:px-6 space-y-12">
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto space-y-4">
        <Badge variant="brand" size="md">
          Our Mission
        </Badge>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-charcoal tracking-tight">
          Find your place. Find your people. Live better together.
        </h1>
        <p className="text-base text-charcoal-muted leading-relaxed">
          Flatmate is built to solve India&apos;s fragmented, stressful urban rental experience by combining
          verified property listings with scientific, 10-dimension roommate lifestyle compatibility.
        </p>
      </div>

      {/* Pillars Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="p-6 space-y-3 border-warm-200">
          <div className="w-12 h-12 rounded-xl bg-pale-green/40 text-forest flex items-center justify-center">
            <Compass className="w-6 h-6" />
          </div>
          <h3 className="text-lg font-bold text-charcoal">Real Accommodations</h3>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            Zero ghost listings and zero bait-and-switch. Every listing is backed by real unit, room, and bed inventory with transparent rent and deposit structures.
          </p>
        </Card>

        <Card className="p-6 space-y-3 border-warm-200">
          <div className="w-12 h-12 rounded-xl bg-pale-green/40 text-forest flex items-center justify-center">
            <Users className="w-6 h-6" />
          </div>
          <h3 className="text-lg font-bold text-charcoal">Lifestyle Compatibility</h3>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            Ten behavioral dimensions—from sleep rhythms and cleanliness to work-from-home habits and social preferences—match you with flatmates you&apos;ll actually thrive with.
          </p>
        </Card>

        <Card className="p-6 space-y-3 border-warm-200">
          <div className="w-12 h-12 rounded-xl bg-pale-green/40 text-forest flex items-center justify-center">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h3 className="text-lg font-bold text-charcoal">Privacy & Scam Defense</h3>
          <p className="text-sm text-charcoal-muted leading-relaxed">
            In compliance with India&apos;s DPDP Act 2023, exact addresses and contact info are fuzzed until visits are confirmed. In-app scam warnings protect you against token money fraud.
          </p>
        </Card>
      </div>

      {/* Call to action */}
      <Card className="p-8 bg-forest text-white text-center space-y-4">
        <h2 className="text-2xl font-bold">Ready to find your next home?</h2>
        <p className="text-sm text-pale-green max-w-xl mx-auto">
          Join thousands of professionals, students, and property owners across Bengaluru, Mumbai, Delhi NCR, Hyderabad, and Pune.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link href="/properties">
            <Button variant="secondary" size="md" className="bg-white text-forest hover:bg-pale-green">
              Explore Discoveries
            </Button>
          </Link>
          <Link href="/flatmates">
            <Button variant="outline" size="md" className="border-white text-white hover:bg-white/10">
              Find Flatmates
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
