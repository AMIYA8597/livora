import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Rooms from current tenants",
  description:
    "Take over a room from a tenant who's moving out, or find a replacement flatmate for your place.",
  alternates: { canonical: "/tenants" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
