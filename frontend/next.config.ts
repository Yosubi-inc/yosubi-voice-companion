import type { NextConfig } from "next";
const config: NextConfig = {
  env: { NEXT_PUBLIC_DEMO_OFFLINE: process.env.DEMO_OFFLINE || "0" },
  async rewrites() {
    return [{ source: "/backend/:path*", destination: `${process.env.BACKEND_URL || "http://127.0.0.1:8000"}/:path*` }];
  },
};
export default config;
