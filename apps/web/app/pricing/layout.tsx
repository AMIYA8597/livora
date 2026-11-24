import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Plans and pricing",
  description:
    "What's free on Flatmate and what the paid plans add for seekers and owners.",
  alternates: { canonical: "/pricing" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
