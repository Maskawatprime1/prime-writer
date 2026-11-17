import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Builds into writer/static/app, served by the Python app at "/" and "/settings".
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: { outDir: "../writer/static/app", emptyOutDir: true, chunkSizeWarningLimit: 1500 },
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8765", "/static": "http://127.0.0.1:8765" } },
});
