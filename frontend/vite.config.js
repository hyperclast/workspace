import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { readFileSync } from "fs";

const pkg = JSON.parse(readFileSync("./package.json", "utf-8"));

export default defineConfig({
  plugins: [svelte()],
  base: "/static/core/spa/",
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  build: {
    manifest: true,
    rollupOptions: {
      input: {
        app: "src/app.js",
        commandPalette: "src/commandPaletteStandalone.js",
        viewer: "src/viewer.js",
      },
      output: {
        entryFileNames: "assets/js/[name]-[hash].js",
        chunkFileNames: "assets/js/[name]-[hash].js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith(".css")) {
            return "assets/css/[name]-[hash].[ext]";
          }
          return "assets/[name]-[hash].[ext]";
        },
      },
    },
    cssCodeSplit: true,
  },
});
