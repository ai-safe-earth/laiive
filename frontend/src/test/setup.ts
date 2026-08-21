import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Both stores are app state as much as any hook is — postAuth.ts keeps the
// promoter's intent in them, and a spec that inherited the previous spec's
// stash would pass or fail for reasons it never wrote down.
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  localStorage.clear();
});
