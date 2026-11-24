import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "PG accommodation",
  description:
    "Compare paying-guest accommodation: rent, meals, rules and availability, with verified operators.",
  alternates: { canonical: "/pg" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
