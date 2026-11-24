import type { Metadata } from "next";

// Signed-in and account pages: never in search results.
export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
