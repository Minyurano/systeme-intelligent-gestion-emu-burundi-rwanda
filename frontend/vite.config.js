import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));

// En développement, les appels /api et /media sont relayés vers Django (port 8000).
export default defineConfig({
  plugins: [react()],
  // Numéro de version affiché dans l'interface (une seule source : package.json)
  define: { __UMURAGE_VERSION__: JSON.stringify(version) },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/media": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.js"],
  },
});
