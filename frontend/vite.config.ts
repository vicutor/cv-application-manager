import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In Docker Compose the backend is a separate container reachable by service
// name, not 127.0.0.1; BACKEND_URL lets compose override this without a
// separate config file for the containerized case.
const backendTarget = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
});
