import Link from "next/link";
import { SearchX } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4 py-12">
      <div className="w-14 h-14 rounded-2xl bg-forest/10 text-forest flex items-center justify-center mb-4">
        <SearchX className="w-7 h-7" />
      </div>
      <h1 className="text-2xl font-bold text-charcoal">Page not found</h1>
      <p className="text-sm text-charcoal-muted mt-2 max-w-sm">
        The page you are looking for has moved, was removed, or never existed.
      </p>
      <div className="mt-6 flex flex-col sm:flex-row gap-3">
        <Link href="/" className="min-h-[44px] inline-flex items-center justify-center px-5 rounded-xl bg-forest text-white text-sm font-semibold">
          Go home
        </Link>
        <Link href="/properties" className="min-h-[44px] inline-flex items-center justify-center px-5 rounded-xl border border-slate-300 text-sm font-semibold text-charcoal">
          Browse properties
        </Link>
      </div>
    </div>
  );
}
