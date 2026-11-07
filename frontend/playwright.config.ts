import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  use: {
    baseURL: "http://127.0.0.1:4173",
    channel: "msedge",
    headless: true,
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run preview",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
    env: { INFOEXPLORER_API_URL: "http://127.0.0.1:18080" },
  },
  reporter: "list",
});
