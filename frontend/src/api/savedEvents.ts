/**
 * Saved events — the uid list in Supabase, the card bodies from the graph.
 *
 * Two halves on purpose. The list is user-scoped rows behind RLS, so it goes
 * straight to Supabase for exactly the reason profile.ts sets out: the rule is
 * already a Postgres policy, and a gateway route would restate it while
 * holding the service-role key. The bodies are deliberately not stored beside
 * it — a saved event is a pointer, and the graph is what an event is, so a
 * corrected price or a moved door time reaches the card. Every open re-reads
 * them through the gateway, which is signed-in only.
 */
import type { EventCard, EventsResult } from "@shared/protocol";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/auth/supabase";
import { apiFetch } from "./client";

/** Matches EVENT_LOOKUP_MAX_UIDS in services/retriever/agent/executor.py. */
export const LOOKUP_CHUNK = 50;

export const savedKeys = {
  uids: (userId: string) => ["saved-uids", userId] as const,
  // Keyed on the SET of uids, not their order: the fetch depends on
  // membership alone (Saved.tsx re-sorts by date anyway), and an
  // order-sensitive key meant every save/unsave — which rewrites the
  // newest-first list — minted a fresh key with an empty cache, refetching
  // every remaining card to remove one that was already on screen.
  cards: (uids: readonly string[]) => ["saved-cards", [...uids].sort().join(",")] as const,
};

/** Newest-saved first: the order the list is read in, decided by Postgres. */
export function useSavedUids(userId: string | undefined) {
  return useQuery({
    queryKey: savedKeys.uids(userId ?? "anonymous"),
    enabled: Boolean(userId),
    queryFn: async (): Promise<string[]> => {
      const { data, error } = await supabase
        .from("saved_events")
        .select("event_uid")
        .eq("user_id", userId!)
        .order("saved_at", { ascending: false });
      if (error) throw new Error(error.message);
      return (data ?? []).map((row) => (row as { event_uid: string }).event_uid);
    },
  });
}

/**
 * Save and unsave are one mutation, and it is optimistic — unlike the profile
 * forms, whose Save button makes a round trip expected. A save pill that waits
 * for the network before it changes reads as broken.
 */
export function useToggleSaved(userId: string | undefined) {
  const queryClient = useQueryClient();
  const key = savedKeys.uids(userId ?? "anonymous");

  return useMutation({
    mutationFn: async ({ uid, next }: { uid: string; next: boolean }) => {
      if (!userId) throw new Error("not signed in");
      if (next) {
        // DO NOTHING on conflict, so a second tab saving the same card is
        // idempotent rather than a 409. Needs only the insert the policy grants.
        const { error } = await supabase
          .from("saved_events")
          .upsert(
            { user_id: userId, event_uid: uid },
            { onConflict: "user_id,event_uid", ignoreDuplicates: true },
          );
        if (error) throw new Error(error.message);
        return;
      }
      const { error } = await supabase
        .from("saved_events")
        .delete()
        .eq("user_id", userId)
        .eq("event_uid", uid);
      if (error) throw new Error(error.message);
    },
    onMutate: async ({ uid, next }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<string[]>(key);
      queryClient.setQueryData<string[]>(key, (current) => {
        const uids = current ?? [];
        return next ? [uid, ...uids.filter((u) => u !== uid)] : uids.filter((u) => u !== uid);
      });
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: key });
    },
  });
}

/**
 * Cards for a set of uids, in chunks the retriever will accept. Exported apart
 * from the hook so the chunking can be tested without a QueryClient.
 */
export async function fetchEventsByUid(uids: string[]): Promise<EventCard[]> {
  const chunks: string[][] = [];
  for (let i = 0; i < uids.length; i += LOOKUP_CHUNK) {
    chunks.push(uids.slice(i, i + LOOKUP_CHUNK));
  }
  // In parallel: 150 saved events are three requests, and serial round trips
  // would triple the wait for nothing — the page re-sorts by date anyway.
  const results = await Promise.all(
    chunks.map(async (chunk) => {
      const response = await apiFetch(`/api/events?uids=${chunk.map(encodeURIComponent).join(",")}`);
      return ((await response.json()) as EventsResult).events;
    }),
  );
  return results.flat();
}

export function useSavedCards(uids: string[] | undefined) {
  return useQuery({
    queryKey: savedKeys.cards(uids ?? []),
    enabled: (uids?.length ?? 0) > 0,
    queryFn: () => fetchEventsByUid(uids!),
  });
}
