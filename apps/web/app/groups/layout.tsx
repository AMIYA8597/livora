import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Flatshare groups",
  description:
    "Team up with others to rent a whole flat together and shortlist places as a group.",
  alternates: { canonical: "/groups" },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
