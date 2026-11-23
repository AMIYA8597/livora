import { LoadingIndicator } from "@flatmate/ui";

/** Full-area spinner for pages waiting on the session or their first data load. */
export function PageLoading({ text = "Loading…" }: { text?: string }) {
  return (
    <div className="min-h-[50vh] flex items-center justify-center px-4" aria-busy="true">
      <LoadingIndicator size="lg" text={text} />
    </div>
  );
}
