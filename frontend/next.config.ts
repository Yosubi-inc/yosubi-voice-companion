import type { NextConfig } from "next";
const config: NextConfig = {
  env: {
    NEXT_PUBLIC_DEMO_OFFLINE: process.env.DEMO_OFFLINE || "0",
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? process.env.BACKEND_URL ?? "",
  },
  output: "export",
};
export default config;
