"use client";

export default function GlobalError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily:
            'Inter, ui-sans-serif, system-ui, -apple-system, sans-serif',
          background: "#fdfcfc",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
        }}
      >
        <div style={{ textAlign: "center", padding: "2rem" }}>
          <h2
            style={{
              fontFamily: 'Georgia, "Times New Roman", serif',
              fontSize: "1.5rem",
              fontWeight: 400,
              marginBottom: "1rem",
            }}
          >
            Something went wrong
          </h2>
          <p style={{ color: "#777169", fontSize: "0.875rem", marginBottom: "1.5rem" }}>
            A critical error occurred. Please try again.
          </p>
          <button
            onClick={() => unstable_retry()}
            style={{
              padding: "0.5rem 1.5rem",
              borderRadius: "9999px",
              background: "#000",
              color: "#fff",
              border: "none",
              fontSize: "0.75rem",
              fontFamily: '"IBM Plex Mono", monospace',
              letterSpacing: "0.05em",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
