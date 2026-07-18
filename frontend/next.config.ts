import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a self-contained server bundle (.next/standalone) for the combined
  // Docker deployment, where it runs alongside the FastAPI backend in one container.
  output: "standalone",
};

export default nextConfig;
