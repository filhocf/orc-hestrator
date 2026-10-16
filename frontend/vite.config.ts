import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Dev proxy: UI runs on 5173, calls /api, which is proxied to the Orc backend.
// The target is overridable via VITE_API_PROXY_TARGET (defaults to the local Orc dev server).
const proxyTarget = process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8005";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
});
