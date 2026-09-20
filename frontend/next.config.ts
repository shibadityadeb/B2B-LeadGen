import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // This project sits inside a directory that has its own lockfile higher up;
  // pin the tracing root so Next does not infer the wrong workspace.
  outputFileTracingRoot: __dirname,
  /* config options here */
};

export default nextConfig;
