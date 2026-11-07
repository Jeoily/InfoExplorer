import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { previewSecurity } from "./preview-security.ts";
const proxy = {
  ...(process.env.INFOEXPLORER_DEBUG_UI === 'true' ? {
    '/__debug': { target: 'http://127.0.0.1:18000' },
  } : {}),
  "/api": {
    target: process.env.INFOEXPLORER_API_URL || "http://127.0.0.1:8080",
  },
};
export default defineConfig({
  define: { __DEBUG_RESEARCH__: process.env.INFOEXPLORER_DEBUG_UI === 'true' },
  plugins: [react(), previewSecurity()],
  base: "./",
  server: { host: "127.0.0.1", port: 5173, strictPort: true, proxy },
  preview: { host: "127.0.0.1", port: 4173, strictPort: true, proxy },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.tsx", "src/**/*.test.ts"],
    setupFiles: ["src/test-setup.ts"],
  },
});
