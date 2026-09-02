/**
 * Organizations and claims (phase D3).
 *
 * Two transports on purpose, split the same way `profile.ts` argues for:
 *
 *  - **Reads and org edits go straight to Supabase.** "A member may read their
 *    organization", "an admin may update it" and "a member may read their
 *    ownerships" are already RLS policies in `20260819000011`, enforced by
 *    Postgres at the point of truth. A gateway route would restate them in
 *    TypeScript while holding the service-role key — so a bug in the restated
 *    check leaks every row instead of none.
 *  - **Claims go through the gateway.** Recording one needs two facts a policy
 *    cannot see: that the caller administers the org, and that the entity
 *    exists in the graph, which lives in Neo4j. `services/gateway/src/orgs.ts`
 *    is where both are visible.
 *
 * Founding an org is the third case: a SECURITY DEFINER RPC, called directly,
 * because the pro floor and the owner seat have to be one transaction.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ArtistHit, VenueHit } from "@shared/protocol";
import { apiFetch } from "./client";
import { fetchEventsByUid } from "./savedEvents";
import { supabase } from "@/auth/supabase";

export type OrgKind = "venue" | "artist" | "promoter";
export type OrgRole = "owner" | "admin" | "member";
export type EntityType = "venue" | "artist" | "event";

export interface Organization {
  id: string;
  kind: OrgKind;
  display_name: string;
  website: string | null;
  phone: string | null;
  contact_email: string | null;
}

/** An organization plus the caller's seat in it. */
export interface OrgMembership extends Organization {
  role: OrgRole;
}

export interface Claim {
  id: string;
  org_id: string;
  entity_type: EntityType;
  entity_uid: string;
  entity_name: string | null;
  basis: "created" | "claimed";
  verified: boolean;
  status: "active" | "revoked";
  created_at: string;
}

export interface RosterSeat {
  user_id: string;
  role: OrgRole;
  created_at: string;
}

/** What `GET /api/claims` answers for one entity — booleans, never rows. */
export interface ClaimState {
  claimed: boolean;
  verified: boolean;
  yours: { id: string; org_id: string; verified: boolean } | null;
}

export const orgKeys = {
  mine: (userId: string) => ["organizations", userId] as const,
  claims: (orgId: string) => ["org-claims", orgId] as const,
  events: (orgId: string, uids: string[]) => ["org-events", orgId, uids] as const,
  roster: (orgId: string) => ["org-roster", orgId] as const,
  entitySearch: (type: EntityType, q: string) => ["entity-search", type, q] as const,
};

/**
 * Membership rows plus their embedded organization, flattened.
 *
 * The filter is not defensive noise: `organizations` comes back null when the
 * embedded row is invisible to the caller's policies, which happens the
 * instant a seat outlives the org it points at. Mapping that to
 * `{...null, role}` would put a roleless, nameless entry on the screen.
 */
export function toMemberships(data: unknown): OrgMembership[] {
  const rows = (data ?? []) as { role: OrgRole; organizations: Organization | null }[];
  return rows
    .filter((row): row is { role: OrgRole; organizations: Organization } =>
      Boolean(row.organizations),
    )
    .map((row) => ({ ...row.organizations, role: row.role }));
}

/**
 * The organizations this account belongs to, with its seat in each.
 *
 * One query rather than two: the membership row carries the role and the
 * embedded organization carries the rest, and PostgREST resolves the foreign
 * key. Both tables are behind "member" policies, so this returns nothing for
 * an account that belongs to nothing — which is the state /pro/org opens in.
 */
export function useMyOrgs(userId: string | undefined) {
  return useQuery({
    queryKey: orgKeys.mine(userId ?? "anonymous"),
    enabled: Boolean(userId),
    queryFn: async (): Promise<OrgMembership[]> => {
      const { data, error } = await supabase
        .from("organization_members")
        .select("role, organizations (id, kind, display_name, website, phone, contact_email)")
        .eq("user_id", userId!);
      if (error) throw new Error(error.message);
      return toMemberships(data);
    },
  });
}

export interface CreateOrgInput {
  kind: OrgKind;
  display_name: string;
  website?: string | null;
  phone?: string | null;
  contact_email?: string | null;
}

export function useCreateOrg(userId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateOrgInput): Promise<string> => {
      // p_ prefixes: plpgsql resolves a bare `display_name` inside the
      // function's INSERT to the parameter rather than the column, so the
      // migration names them apart and PostgREST mirrors that here.
      const { data, error } = await supabase.rpc("create_organization", {
        p_kind: input.kind,
        p_display_name: input.display_name,
        p_website: input.website ?? null,
        p_phone: input.phone ?? null,
        p_contact_email: input.contact_email ?? null,
      });
      if (error) throw new Error(error.message);
      return data as string;
    },
    onSuccess: () => {
      if (userId) void queryClient.invalidateQueries({ queryKey: orgKeys.mine(userId) });
    },
  });
}

export type OrgPatch = Partial<Pick<Organization, "display_name" | "website" | "phone" | "contact_email">>;

export function useUpdateOrg(userId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ orgId, patch }: { orgId: string; patch: OrgPatch }) => {
      // Column grants (migration 22) mean `kind` and `created_by` are refused
      // by Postgres even if this ever tried to send them.
      const { error } = await supabase
        .from("organizations")
        .update({ ...patch, updated_at: new Date().toISOString() })
        .eq("id", orgId);
      if (error) throw new Error(error.message);
    },
    onSuccess: () => {
      if (userId) void queryClient.invalidateQueries({ queryKey: orgKeys.mine(userId) });
    },
  });
}

/** Live claims held by one organization. Revoked rows stay out of the screen. */
export function useOrgClaims(orgId: string | undefined) {
  return useQuery({
    queryKey: orgKeys.claims(orgId ?? "none"),
    enabled: Boolean(orgId),
    queryFn: async (): Promise<Claim[]> => {
      const { data, error } = await supabase
        .from("entity_ownership")
        .select(
          "id, org_id, entity_type, entity_uid, entity_name, basis, verified, status, created_at",
        )
        .eq("org_id", orgId!)
        .eq("status", "active")
        .order("created_at", { ascending: false });
      if (error) throw new Error(error.message);
      return (data ?? []) as Claim[];
    },
  });
}

/**
 * Full cards for the events an organisation owns.
 *
 * `entity_ownership` denormalizes only a name, which is enough for a review
 * queue and not enough for a promoter checking their own calendar - a list of
 * bare titles cannot tell two dates of the same night apart. The uids are
 * exchanged for cards through the read path /saved already uses.
 */
export function useOrgEvents(orgId: string | undefined, uids: string[]) {
  return useQuery({
    queryKey: orgKeys.events(orgId ?? "none", uids),
    enabled: Boolean(orgId) && uids.length > 0,
    queryFn: () => fetchEventsByUid(uids),
  });
}

/** Read-only until the invitation routes land (phase D2 tail). */
export function useRoster(orgId: string | undefined) {
  return useQuery({
    queryKey: orgKeys.roster(orgId ?? "none"),
    enabled: Boolean(orgId),
    queryFn: async (): Promise<RosterSeat[]> => {
      const { data, error } = await supabase
        .from("organization_members")
        .select("user_id, role, created_at")
        .eq("org_id", orgId!);
      if (error) throw new Error(error.message);
      return (data ?? []) as RosterSeat[];
    },
  });
}

/**
 * Venue or artist search for the claim picker, through the gateway's pro-gated
 * proxy to the retriever. Events are not searchable by name here: a promoter
 * claims the room or the act, and their events follow from publishing.
 */
export function useEntitySearch(type: Exclude<EntityType, "event">, query: string) {
  const fragment = query.trim();
  return useQuery({
    queryKey: orgKeys.entitySearch(type, fragment),
    // The retriever refuses a one-character fragment; asking anyway would
    // spend a round trip to be told so.
    enabled: fragment.length >= 2,
    queryFn: async (): Promise<(VenueHit | ArtistHit)[]> => {
      const path = type === "venue" ? "venues" : "artists";
      const response = await apiFetch(`/api/${path}?q=${encodeURIComponent(fragment)}`);
      const body = (await response.json()) as Record<string, (VenueHit | ArtistHit)[]>;
      return body[path] ?? [];
    },
  });
}

export interface ClaimInput {
  org_id: string;
  entity_type: EntityType;
  entity_uid: string;
}

export function useCreateClaim(orgId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: ClaimInput): Promise<Claim> => {
      const response = await apiFetch("/api/claims", {
        method: "POST",
        body: JSON.stringify(input),
      });
      return (await response.json()) as Claim;
    },
    onSuccess: () => {
      if (orgId) void queryClient.invalidateQueries({ queryKey: orgKeys.claims(orgId) });
    },
  });
}

export function useWithdrawClaim(orgId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (claimId: string) => {
      await apiFetch(`/api/claims/${encodeURIComponent(claimId)}`, { method: "DELETE" });
    },
    onSuccess: () => {
      if (orgId) void queryClient.invalidateQueries({ queryKey: orgKeys.claims(orgId) });
    },
  });
}

/** Whether an entity is already spoken for — the per-hit state in the picker. */
export async function fetchClaimState(
  entityType: EntityType,
  entityUid: string,
): Promise<ClaimState> {
  const response = await apiFetch(
    `/api/claims?entity_type=${encodeURIComponent(entityType)}&entity_uid=${encodeURIComponent(entityUid)}`,
  );
  return (await response.json()) as ClaimState;
}
