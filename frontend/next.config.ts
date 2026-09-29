import type { NextConfig } from "next";
import path from "path";

/** Silk serves a static export from document-root (no Node Unit app). */
const silkStatic = process.env.SILK_STATIC === "1";

const nextConfig: NextConfig = {
  output: silkStatic ? "export" : "standalone",
  // Apache/Silk document-root serves calc/index.html for /calc/ more reliably
  // than calc.html for /calc.
  trailingSlash: silkStatic ? true : undefined,
  // Let Silk/Apache own Content-Encoding when a Node server is used.
  compress: false,
  images: silkStatic ? { unoptimized: true } : undefined,
  // Explicit alias so production builds resolve @/* even when tsconfig paths
  // are not picked up (seen on some Linux / Silk environments).
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      "@": path.join(__dirname, "src"),
    };
    return config;
  },
};

export default nextConfig;
