import { randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Plugin } from "vite";
// Local build preview only; Java deployment must provide its own per-response nonce.
export function previewSecurity(): Plugin {
  return {
    name: "local-preview-security",
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        const path = (req.url || "/").split("?")[0];
        if (path !== "/" && path !== "/index.html") return next();
        const nonce = randomBytes(24).toString("base64");
        const html = readFileSync(
          resolve(server.config.root, server.config.build.outDir, "index.html"),
          "utf8",
        );
        res.setHeader("Content-Type", "text/html; charset=utf-8");
        res.setHeader("Cache-Control", "no-store");
        res.setHeader("X-Content-Type-Options", "nosniff");
        res.setHeader("Referrer-Policy", "no-referrer");
        res.setHeader(
          "Content-Security-Policy",
          `default-src 'self'; script-src 'self'; style-src 'self' 'nonce-${nonce}'; style-src-attr 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'`,
        );
        res.end(
          html.replace(
            "<head>",
            `<head><meta name="csp-nonce" content="${nonce}">`,
          ),
        );
      });
    },
  };
}
