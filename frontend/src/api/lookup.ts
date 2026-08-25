import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { VenueLookupResult } from "@shared/protocol";
import { apiFetch } from "./client";

/**
 * Entity lookups for pickers — the pro form's venue combobox today, the org
 * screen's claim search next. Pro-gated at the gateway, so nothing here is
 * reachable signed out.
 */

/**
 * The client-side shadow of the graph's `norm`: lowercase, accents folded,
 * whitespace collapsed. Enough to tell whether two spellings name the same
 * venue, which is all the form's pick-retention compare needs.
 */
export function foldName(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

/** Trailing-edge debounce, so a typing burst costs one request, not one per key. */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/**
 * Venues by name fragment, scoped to the typed city when there is one.
 * Two characters is the server's floor (400 below it), so it is the
 * `enabled` floor here too — the refusal is never even sent.
 */
export function useVenueLookup(
  q: string,
  city: string | null | undefined,
  enabled = true,
) {
  const query = useDebouncedValue(q.trim(), 300);
  // The scope debounces too: retyping the city must not fire one Aura scan
  // per keystroke just because the venue fragment happened to be settled.
  const scope = useDebouncedValue((city ?? "").trim(), 300);
  return useQuery({
    queryKey: ["venues", query.toLowerCase(), scope.toLowerCase()],
    enabled: enabled && query.length >= 2,
    staleTime: 60_000,
    queryFn: async (): Promise<VenueLookupResult> => {
      const params = new URLSearchParams({ q: query });
      if (scope) params.set("city", scope);
      const response = await apiFetch(`/api/venues?${params.toString()}`);
      return (await response.json()) as VenueLookupResult;
    },
  });
}
