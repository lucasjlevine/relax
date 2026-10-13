import type { NextConfig } from "next";
import path from "path";

/**
 * Silk: Next (Unit/Node) owns the site. FastAPI runs on localhost via
 * systemd; rewrites proxy browser /api/* → that process.
 */
const silkDeploy = process.env.SILK_DEPLOY === "1";
const apiUpstream =
  process.env.RELAX_API_UPSTREAM || "http://127.0.0.1:8000";

// Local next dev talks to uvicorn on :8000 (cross-origin). Silk uses same-origin
// `/api` rewrites, so `'self'` alone is enough there — keep localhost ports so a
// mis-set NEXT_PUBLIC_API_URL cannot hard-break the calculator.
const connectSrc = [
  "'self'",
  "http://localhost:8000",
  "http://127.0.0.1:8000",
  "ws://localhost:3000",
  "ws://127.0.0.1:3000",
].join(" ");

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      `connect-src ${connectSrc}`,
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  output: "standalone",
  compress: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
  async rewrites() {
    if (!silkDeploy) return [];
    return [
      {
        source: "/api/:path*",
        destination: `${apiUpstream}/api/:path*`,
      },
    ];
  },
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      "@": path.join(__dirname, "src"),
    };
    return config;
  },
};

export default nextConfig;
