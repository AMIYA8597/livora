import type { Metadata } from "next";

export const metadata: Metadata = {
  // The root template names the site on this title; pages below set their own and get the
  // same suffix from this template.
  title: { default: "Find flatmates", template: "%s | Flatmate" },
  description:
    "Meet people looking for a flatmate, matched on lifestyle: sleep schedule, cleanliness, work hours, food and more.",
  alternates: { canonical: "/flatmates" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
