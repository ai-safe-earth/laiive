import path from "node:path";
import react from "@vitejs/plugin-react-swc";
import { defineConfig } from "vite";

// The protocol types come straight from services/shared/ts/protocol.ts (D10) —
// the same file tests/test_ts_contract.py diffs against the pydantic models, so
// the frontend cannot drift from the wire format. It lives outside this root,
// hence the explicit fs.allow entry.
const sharedTs = path.resolve(__dirname, "../services/shared/ts");

export default defineConfig({
  server: {
    // 8080 is taken by EnterpriseDB on the dev machine
    port: 8081,
    strictPort: true,
    fs: { allow: [path.resolve(__dirname), sharedTs] },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@shared": sharedTs,
    },
  },
});
