import type { NextConfig } from "next";
import path from "path";

/**
 * Silk: static export under /relax/ (no Node Unit app — Unit’s Node adapter
 * breaks Next App Router). API stays on /relax-api via Python Unit.
 */
const silkDeploy = process.env.SILK_DEPLOY === "1";

const nextConfig: NextConfig = {
  output: silkDeploy ? "export" : "standalone",
  basePath: silkDeploy ? "/relax" : undefined,
  trailingSlash: silkDeploy ? true : undefined,
  compress: false,
  images: silkDeploy ? { unoptimized: true } : undefined,
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      "@": path.join(__dirname, "src"),
    };
    return config;
  },
};

export default nextConfig;
