import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "**/*.spec.ts",
  use: { baseURL: "http://127.0.0.1:3000", browserName: "chromium", launchOptions: { args: ["--use-fake-device-for-media-stream"] } },
  webServer: {
    command: "npm --prefix ../frontend run dev",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: false,
    timeout: 120000,
    env: { NEXT_PUBLIC_TTS_URL: "http://127.0.0.1:9/" },
  },
});
