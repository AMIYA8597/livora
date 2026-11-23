"use client";

import { useEffect } from "react";
import Link from "next/link";
import { ErrorState } from "@flatmate/ui";

/** Catches render/runtime errors in any route below the root layout; navbar and footer stay. */
export default function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Route error", error.digest ?? "", error.message);
  }, [error]);

  return (
    <div className="min-h-[50vh] flex flex-col items-center justify-center px-4 py-10">
      <ErrorState
        title="This page hit a problem"
        message="Something went wrong while showing this page. You can try again, or head back home."
        correlationId={error.digest}
        onRetry={reset}
      />
      <Link href="/" className="text-sm font-semibold text-forest hover:underline">
        Back to home
      </Link>
    </div>
  );
}
