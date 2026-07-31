import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Override when port 8080 is taken locally, for example by an existing Apache:
//   VITE_PROXY_TARGET=http://127.0.0.1:8081 npm run dev
const apiTarget = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8080";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": apiTarget,
      "/health": apiTarget,
    },
  },
});
