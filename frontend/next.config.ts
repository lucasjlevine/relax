import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  // Let Silk/Apache own Content-Encoding. Next gzip + front-proxy gzip
  // produces binary garbage in the browser/curl.
  compress: false,
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
