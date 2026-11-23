import { LoadingIndicator } from "@flatmate/ui";

/** Shown by Next.js while a route segment is loading. */
export default function Loading() {
  return (
    <div className="min-h-[50vh] flex items-center justify-center px-4" aria-busy="true">
      <LoadingIndicator size="lg" text="Loading…" />
    </div>
  );
}
