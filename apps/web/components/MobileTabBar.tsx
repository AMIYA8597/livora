"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Compass, Home, LayoutDashboard, LogIn, MessageSquare, Sparkles, Users } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

type Tab = { href: string; label: string; icon: typeof Home; exact?: boolean };

const SIGNED_IN: Tab[] = [
  { href: "/properties", label: "Discover", icon: Compass },
  { href: "/flatmates", label: "Flatmates", icon: Users },
  { href: "/matches", label: "Matches", icon: Sparkles },
  { href: "/messages", label: "Messages", icon: MessageSquare },
  { href: "/dashboard", label: "My Space", icon: LayoutDashboard },
];

const SIGNED_OUT: Tab[] = [
  { href: "/", label: "Home", icon: Home, exact: true },
  { href: "/properties", label: "Discover", icon: Compass },
  { href: "/flatmates", label: "Flatmates", icon: Users },
  { href: "/login", label: "Sign in", icon: LogIn },
];

/** Auth screens are focused flows; the tab bar would only distract. */
const HIDDEN_ON = ["/login", "/register", "/forgot-password", "/reset-password", "/onboarding"];

/**
 * Bottom navigation for phones and small tablets (below the `lg` breakpoint, where the top bar
 * collapses into a menu). Renders its own spacer so page content and the footer are never hidden
 * behind it, and respects the iOS home-indicator safe area.
 */
export function MobileTabBar() {
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading || HIDDEN_ON.some((p) => pathname.startsWith(p))) return null;
  const tabs = isAuthenticated ? SIGNED_IN : SIGNED_OUT;

  return (
    <>
      <div aria-hidden className="lg:hidden h-[calc(4rem+env(safe-area-inset-bottom))]" />
      <nav
        aria-label="Primary"
        className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur-md border-t border-warm-200 pb-[env(safe-area-inset-bottom)]"
      >
        <ul className="flex h-16">
          {tabs.map(({ href, label, icon: Icon, exact }) => {
            const active = exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
            return (
              <li key={href} className="flex-1">
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`h-full flex flex-col items-center justify-center gap-0.5 text-[11px] font-semibold transition-colors ${
                    active ? "text-forest" : "text-charcoal-muted hover:text-charcoal"
                  }`}
                >
                  <Icon className={`w-5 h-5 ${active ? "text-forest" : ""}`} />
                  <span>{label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}
