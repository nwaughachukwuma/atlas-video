import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [tailwindcss(), svelte()],
  base: "/ui",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    // Proxy API requests to the Atlas backend during development
    proxy: {
      "/health": "http://localhost:8000",
      "/transcribe": "http://localhost:8000",
      "/extract": "http://localhost:8000",
      "/index": "http://localhost:8000",
      "/search": "http://localhost:8000",
      "/chat": "http://localhost:8000",
      "/list-videos": "http://localhost:8000",
      "/list-chat": "http://localhost:8000",
      "/get-video": "http://localhost:8000",
      "/stats": "http://localhost:8000",
      "/queue": "http://localhost:8000",
    },
  },
});
