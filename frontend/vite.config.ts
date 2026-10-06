import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// API requests and product images are forwarded to the FastAPI backend on port 8000.
const proxy = {
  "/api": "http://localhost:8000",
  "/media": "http://localhost:8000",
};

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
});
