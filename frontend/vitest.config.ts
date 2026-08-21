import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

/**
 * Tests inherit the app's resolution — the `@`, `@shared` and `@brand` aliases
 * — so a spec imports exactly what the app imports and cannot drift from it.
 *
 * `env` stands in for the real .env: src/env.ts fails loudly on a missing key
 * by design, and a test run is not a place to require real credentials. The
 * values are never dialled; every spec that touches Supabase mocks the client.
 */
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      restoreMocks: true,
      env: {
        VITE_API_URL: "http://localhost:8000",
        VITE_SUPABASE_URL: "http://localhost:54321",
        VITE_SUPABASE_PUBLISHABLE_KEY: "test-publishable-key",
      },
    },
  }),
);
