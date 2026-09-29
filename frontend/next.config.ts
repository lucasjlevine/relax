import type { NextConfig } from "next";
import path from "path";

/** Silk: UI under /relax, API under /relax-api (non-overlapping Unit URIs). */
const silkDeploy = process.env.SILK_DEPLOY === "1";

const nextConfig: NextConfig = {
  output: "standalone",
  basePath: silkDeploy ? "/relax" : undefined,
  // Let Silk/Apache own Content-Encoding.
  compress: false,
  // Explicit alias so production builds resolve @/* on Linux / Silk.
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      "@": path.join(__dirname, "src"),
    };
    return config;
  },
};

export default nextConfig;
