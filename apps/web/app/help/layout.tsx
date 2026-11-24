import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Help",
  description:
    "Answers to common questions about finding a place, listing one, staying safe and your account.",
  alternates: { canonical: "/help" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
