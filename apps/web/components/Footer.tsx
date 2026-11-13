import React from "react";
import Link from "next/link";
import { Home, ShieldCheck, Heart } from "lucide-react";

export const Footer: React.FC = () => {
  return (
    <footer className="bg-slate-900 text-slate-400 py-12 border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white">
                <Home className="w-4 h-4" />
              </div>
              <span className="font-bold text-lg text-white">flatmate.</span>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">
              The modern way to find compatible roommates, explore co-living spaces, and team up for rental homes.
            </p>
          </div>

          {/* Discovery */}
          <div>
            <h4 className="text-white font-semibold mb-3 text-sm tracking-wider uppercase">Discover</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/properties" className="hover:text-white transition-colors">Shared Apartments</Link></li>
              <li><Link href="/flatmates" className="hover:text-white transition-colors">Flatmate Directory</Link></li>
              <li><Link href="/matches" className="hover:text-white transition-colors">Compatibility Quiz</Link></li>
              <li><Link href="/groups" className="hover:text-white transition-colors">Team-Up Groups</Link></li>
            </ul>
          </div>

          {/* Trust & Safety */}
          <div>
            <h4 className="text-white font-semibold mb-3 text-sm tracking-wider uppercase">Trust & Safety</h4>
            <ul className="space-y-2 text-sm">
              <li className="flex items-center space-x-1.5 text-emerald-400">
                <ShieldCheck className="w-4 h-4" />
                <span>Verified Identities</span>
              </li>
              <li><Link href="/docs/SECURITY.md" className="hover:text-white transition-colors">Safety Guidelines</Link></li>
              <li><Link href="#" className="hover:text-white transition-colors">Scam Prevention</Link></li>
              <li><Link href="#" className="hover:text-white transition-colors">Rental Agreements</Link></li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="text-white font-semibold mb-3 text-sm tracking-wider uppercase">Platform</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/docs/PRD.md" className="hover:text-white transition-colors">About Us</Link></li>
              <li><Link href="/docs/API_DESIGN.md" className="hover:text-white transition-colors">API & Integrations</Link></li>
              <li><Link href="#" className="hover:text-white transition-colors">Privacy Policy</Link></li>
              <li><Link href="#" className="hover:text-white transition-colors">Terms of Service</Link></li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500">
          <p>© {new Date().getFullYear()} Flatmate Platform, Inc. All rights reserved.</p>
          <p className="flex items-center space-x-1 mt-2 sm:mt-0">
            <span>Built with precision &</span>
            <Heart className="w-3.5 h-3.5 text-rose-500 fill-rose-500" />
            <span>for urban co-livers.</span>
          </p>
        </div>
      </div>
    </footer>
  );
};
