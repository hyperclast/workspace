import { defineConfig } from "vitest/config";
import { readFileSync } from "fs";

const pkg = JSON.parse(readFileSync("./package.json", "utf-8"));

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  test: {
    environment: "happy-dom",
    globals: true,
    exclude: [
      "**/node_modules/**",
      "**/dist/**",
      "**/cypress/**",
      "**/.{idea,git,cache,output,temp}/**",
      "**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build}.config.*",
      "**/tests/e2e/**", // Exclude Playwright e2e tests
    ],
  },
});
