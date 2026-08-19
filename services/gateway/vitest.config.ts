import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    testTimeout: 15_000,
    hookTimeout: 15_000,
    // both files spin real HTTP servers; parallel cold-start on this machine
    // pushes the SSE timing test past its timeout
    fileParallelism: false,
  },
});
