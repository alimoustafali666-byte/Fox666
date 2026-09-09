"use client";

/** Last-resort boundary: catches errors thrown by the root layout
 *  itself, which is the one case where the providers -- theme, locale,
 *  auth -- are not available. It therefore renders its own <html> and
 *  <body> and uses literal English text rather than t(), because the
 *  translation dictionary is reached through a provider that may be
 *  exactly what failed. Every other error is handled by the localized
 *  boundary at app/(app)/error.tsx. */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en" dir="ltr">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          background: "#080c1a",
          color: "#e8ecf8",
          fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
          padding: "24px",
        }}
      >
        <div style={{ maxWidth: "420px", textAlign: "center" }}>
          <h1 style={{ fontSize: "20px", marginBottom: "8px" }}>UAE AI Office could not start</h1>
          <p style={{ fontSize: "14px", lineHeight: 1.6, color: "#9aa6c4" }}>
            An unexpected error stopped the application from loading. Reload to try again.
            {error.digest ? ` Error reference: ${error.digest}.` : ""}
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: "16px",
              padding: "10px 20px",
              borderRadius: "10px",
              border: "1px solid #2b3a63",
              background: "#1b5cff",
              color: "#fff",
              fontSize: "14px",
              cursor: "pointer",
            }}
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
