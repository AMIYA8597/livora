import React from "react";
import Link from "next/link";
import { Compass, ShieldCheck, Heart } from "lucide-react";

export const Footer: React.FC = () => {
  return (
    <footer className="bg-charcoal text-slate-400 py-12 border-t border-charcoal-light">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="space-y-4">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-lg bg-forest flex items-center justify-center text-white shadow-sm">
                <Compass className="w-4 h-4 text-pale-green" />
              </div>
              <span className="font-bold text-lg text-white">
                flatmate<span className="text-secondary-green">.</span>
              </span>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">
              Find your place. Find your people. Live better together.
              The modern Indian rental platform powered by 10-D lifestyle compatibility and verified listings.
            </p>
          </div>

          {/* Discovery */}
          <div>
            <h4 className="text-white font-semibold mb-3 text-sm tracking-wider uppercase">Discover</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <Link href="/properties" className="hover:text-white transition-colors">
                  Properties & Shared Flats
                </Link>
              </li>
              <li>
                <Link href="/flatmates" className="hover:text-white transition-colors">
                  Flatmate Directory
                </Link>
              </li>
              <li>
                <Link href="/matches" className="hover:text-white transition-colors">
                  AI Compatibility Matches
                </Link>
              </li>
              <li>
                <Link href="/groups" className="hover:text-white transition-colors">
                  Team-Up Groups & Wishlists
                </Link>
              </li>
            </ul>
          </div>

          {/* Trust & Safety */}
          <div>
            <h4 className="text-white font-semibold mb-3 text-sm tracking-wider uppercase">Trust & Safety</h4>
            <ul className="space-y-2 text-sm">
              <li className="flex items-center space-x-1.5 text-pale-green">
                <ShieldCheck className="w-4 h-4" />
                <span>Verified Identities</span>
              </li>
              <li>
                <Link href="/safety" className="hover:text-white transition-colors">
                  Safety & Scam Defense
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="hover:text-white transition-colors">
                  DPDP Location Fuzzing
                </Link>
              </li>
              <li>
                <Link href="/help" className="hover:text-white transition-colors">
                  Listing Guidelines
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal & Help */}
          <div>
            <h4 className="text-white font-semibold mb-3 text-sm tracking-wider uppercase">Platform</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <Link href="/about" className="hover:text-white transition-colors">
                  About Flatmate
                </Link>
              </li>
              <li>
                <Link href="/pricing" className="hover:text-white transition-colors">
                  Plans
                </Link>
              </li>
              <li>
                <Link href="/help" className="hover:text-white transition-colors">
                  Help & FAQs
                </Link>
              </li>
              <li>
                <Link href="/terms" className="hover:text-white transition-colors">
                  Terms of Service
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="hover:text-white transition-colors">
                  Privacy Policy
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-charcoal-light flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500">
          <p>© {new Date().getFullYear()} Flatmate Platform. All rights reserved.</p>
          <p className="flex items-center space-x-1 mt-2 sm:mt-0">
            <span>Crafted for urban shared living in India.</span>
          </p>
        </div>
      </div>
    </footer>
  );
};
