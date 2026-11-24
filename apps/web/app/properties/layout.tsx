import type { Metadata } from "next";

export const metadata: Metadata = {
  // The root template names the site on this title; pages below set their own and get the
  // same suffix from this template.
  title: { default: "Rooms, flats and PGs for rent", template: "%s | Flatmate" },
  description:
    "Browse verified rooms, flats and PGs for rent across Bengaluru, Mumbai, Delhi NCR, Pune, Hyderabad and Chennai, with rent, deposit and move-in dates up front.",
  alternates: { canonical: "/properties" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
