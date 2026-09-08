export type UserRole = "user" | "pro" | "admin";

export interface AuthUser {
  id: string;
  role: UserRole;
  /**
   * The verified `email` claim, absent only if the token carries none.
   *
   * Read by exactly one route: accepting an invitation, which must refuse a
   * link redeemed by an address it was not sent to. Everything else identifies
   * people by `id` and should keep doing so.
   */
  email?: string;
}

declare module "fastify" {
  interface FastifyRequest {
    /** Verified identity; null = anonymous (no Authorization header). */
    user: AuthUser | null;
  }
}
