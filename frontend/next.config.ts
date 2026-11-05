import type { NextConfig } from "next";

// Build id for the service-worker cache name: the deploy's commit on Vercel,
// the build time elsewhere. Any value that changes per build will do.
const buildId =
  process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 12) ?? String(Date.now());

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_BUILD_ID: buildId,
  },
  // Audiotool rejects `localhost` in OAuth redirect URIs, so development runs
  // on 127.0.0.1. Next.js treats that as a cross-origin dev host and blocks
  // its dev resources (HMR, fonts) by default, which stops the client from
  // hydrating at all — allow it explicitly.
  allowedDevOrigins: ["127.0.0.1"],
  experimental: {
    proxyClientMaxBodySize: "25mb",
  },
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
      // Readiness probe, used by the login page to wake a scaled-to-zero backend.
      {
        source: "/ready",
        destination: `${apiUrl}/ready`,
      },
    ];
  },
};

export default nextConfig;
