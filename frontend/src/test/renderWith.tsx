import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ComponentProps, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { LanguageProvider } from "@/i18n/useTranslation";

/** A path, or a `{ pathname, state }` entry for a screen that reads router state.
 *  Read off MemoryRouter rather than imported: react-router-dom does not
 *  re-export `InitialEntry`. */
type Route = NonNullable<ComponentProps<typeof MemoryRouter>["initialEntries"]>[number];

/**
 * The three providers every screen in this app sits under, in one place.
 * Thirteen specs each hand-rolled this stack, and they had already drifted on
 * nesting order and on whether retries were off.
 *
 * Retries are off: a spec asserting an error state should not first wait out
 * three exponential backoffs, and a fresh client per render keeps one spec's
 * cache out of the next one's.
 *
 * `ui` can be a component or a whole `<Routes>` — pass `route` when the screen
 * reads the path (a `:param`, a `?next=`, or router state).
 *
 * `rerender` re-wraps, so a spec can hand the same tree new props without
 * losing the providers it was mounted under.
 */
export function renderWith(ui: ReactNode, { route = "/" }: { route?: Route } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrap = (node: ReactNode) => (
    <QueryClientProvider client={client}>
      <LanguageProvider>
        <MemoryRouter initialEntries={[route]}>{node}</MemoryRouter>
      </LanguageProvider>
    </QueryClientProvider>
  );
  const result = render(wrap(ui));
  return { ...result, rerender: (node: ReactNode) => result.rerender(wrap(node)) };
}
