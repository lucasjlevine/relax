import type { NextConfig } from "next";
import path from "path";

/**
 * Silk: Next (Unit/Node) owns the site. FastAPI runs on localhost via
 * systemd; rewrites proxy browser /api/* → that process.
 */
const silkDeploy = process.env.SILK_DEPLOY === "1";
const apiUpstream =
  process.env.RELAX_API_UPSTREAM || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  compress: false,
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
