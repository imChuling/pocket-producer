import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
    ];
  },
};

export default nextConfig;
