/**
 * Profile and promoter data — the one place that talks to Supabase tables.
 *
 * Deliberately NOT routed through the gateway. The rule "a user may read and
 * write only their own row" is already expressed as RLS policy in
 * supabase/migrations/20260813000001_profiles.sql and 20260813000003, enforced
 * by Postgres at the point of truth. A gateway route would restate that rule in
 * TypeScript — and since the gateway holds the service-role key, it would run
 * with RLS bypassed, so a bug in the restated check leaks every row instead of
 * one. The hop buys nothing either: the publishable key and the user's JWT are
 * already in the browser for auth.
 *
 * Everything is behind this module, so moving it server-side later (audit
 * trail, quota coupling) is a change of implementation, not of call sites.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/auth/supabase";
import type { Language } from "@/i18n/translations";

export interface Profile {
  id: string;
  display_name: string | null;
  ui_language: Language;
}

export interface PromoterProfile {
  user_id: string;
  org_name: string;
  website: string | null;
  phone: string | null;
  managed_venues: string[];
  managed_artists: string[];
  notes: string | null;
}

export const profileKeys = {
  profile: (userId: string) => ["profile", userId] as const,
  promoter: (userId: string) => ["promoter-profile", userId] as const,
};

/** A jsonb array of free-form entries; anything unexpected reads as empty. */
function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

export function useProfile(userId: string | undefined) {
  return useQuery({
    queryKey: profileKeys.profile(userId ?? "anonymous"),
    enabled: Boolean(userId),
    queryFn: async (): Promise<Profile | null> => {
      const { data, error } = await supabase
        .from("profiles")
        .select("id, display_name, ui_language")
        .eq("id", userId!)
        .maybeSingle();
      if (error) throw new Error(error.message);
      return data as Profile | null;
    },
  });
}

export function useUpdateProfile(userId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (patch: Partial<Pick<Profile, "display_name" | "ui_language">>) => {
      if (!userId) throw new Error("not signed in");
      const { error } = await supabase
        .from("profiles")
        .update({ ...patch, updated_at: new Date().toISOString() })
        .eq("id", userId);
      if (error) throw new Error(error.message);
    },
    onSuccess: () => {
      if (userId) {
        void queryClient.invalidateQueries({ queryKey: profileKeys.profile(userId) });
      }
    },
  });
}

export function usePromoterProfile(userId: string | undefined) {
  return useQuery({
    queryKey: profileKeys.promoter(userId ?? "anonymous"),
    enabled: Boolean(userId),
    queryFn: async (): Promise<PromoterProfile | null> => {
      const { data, error } = await supabase
        .from("promoter_profiles")
        .select("user_id, org_name, website, phone, managed_venues, managed_artists, notes")
        .eq("user_id", userId!)
        .maybeSingle();
      if (error) throw new Error(error.message);
      if (!data) return null;
      return {
        ...(data as PromoterProfile),
        managed_venues: stringList((data as { managed_venues: unknown }).managed_venues),
        managed_artists: stringList((data as { managed_artists: unknown }).managed_artists),
      };
    },
  });
}

export type PromoterProfileInput = Omit<PromoterProfile, "user_id">;

export function useSavePromoterProfile(userId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: PromoterProfileInput) => {
      if (!userId) throw new Error("not signed in");
      // Upsert: a pro who never filled this in has no row yet, and the RLS
      // policies allow both the insert and the update of their own row.
      const { error } = await supabase.from("promoter_profiles").upsert(
        {
          user_id: userId,
          ...input,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "user_id" },
      );
      if (error) throw new Error(error.message);
    },
    onSuccess: () => {
      if (userId) {
        void queryClient.invalidateQueries({ queryKey: profileKeys.promoter(userId) });
      }
    },
  });
}
