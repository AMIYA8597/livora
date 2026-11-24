import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { MobileTabBar } from "@/components/MobileTabBar";
import { indexable, siteUrl } from "@/lib/site";

export const viewport: Viewport = {
  themeColor: "#173D32",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  // Lets the tab bar and chat composer sit clear of the iPhone home indicator.
  viewportFit: "cover",
};

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  title: {
    default: "Flatmate | Find your place. Find your people. Live better together.",
    template: "%s | Flatmate",
  },
  description:
    "Intelligent flatmate compatibility and verified rental accommodation marketplace across Bengaluru, Mumbai, Delhi NCR, Pune, Hyderabad, and Chennai.",
  keywords: [
    "flatmate",
    "roommate matching",
    "rental flat",
    "1BHK",
    "2BHK",
    "PG accommodation",
    "Bangalore flatmates",
    "Mumbai flat sharing",
    "shared apartments India",
    "verified landlords",
  ],
  authors: [{ name: "Flatmate Platform" }],
  creator: "Flatmate Platform",
  openGraph: {
    type: "website",
    locale: "en_IN",
    url: "/",
    title: "Flatmate | Find your place. Find your people. Live better together.",
    description:
      "Transforming rental living in India with 10-dimension compatibility scoring, verified listings, and direct tenant connections.",
    siteName: "Flatmate Platform",
  },
  twitter: {
    card: "summary_large_image",
    title: "Flatmate | Find your place. Find your people. Live better together.",
    description:
      "Vector lifestyle matching and verified accommodations across major Indian cities.",
  },
  // Only the production site is indexed; staging and local builds say noindex.
  robots: indexable()
    ? {
        index: true,
        follow: true,
        googleBot: { index: true, follow: true, "max-video-preview": -1, "max-image-preview": "large", "max-snippet": -1 },
      }
    : { index: false, follow: false },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-warm font-sans antialiased text-charcoal">
        <Navbar />
        <main className="flex-1" id="main-content">{children}</main>
        <Footer />
        <MobileTabBar />
      </body>
    </html>
  );
}
