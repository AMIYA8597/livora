"use client";

/** Last resort when the root layout itself fails; must render its own <html>. */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", margin: 0, padding: 16, background: "#FAF7F2", color: "#1F2937" }}>
        <div style={{ textAlign: "center", maxWidth: 420 }}>
          <h1 style={{ fontSize: 22, marginBottom: 8 }}>Flatmate is having trouble</h1>
          <p style={{ fontSize: 14, opacity: 0.8 }}>Please try again in a moment.</p>
          {error.digest && <p style={{ fontSize: 12, fontFamily: "monospace", opacity: 0.6 }}>Ref ID: {error.digest}</p>}
          <button onClick={reset} style={{ marginTop: 16, minHeight: 44, padding: "0 20px", borderRadius: 12, border: 0, background: "#173D32", color: "#fff", fontWeight: 600, cursor: "pointer" }}>
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
