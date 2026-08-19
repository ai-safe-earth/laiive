export type UserRole = "user" | "pro" | "admin";

export interface AuthUser {
  id: string;
  role: UserRole;
}

declare module "fastify" {
  interface FastifyRequest {
    /** Verified identity; null = anonymous (no Authorization header). */
    user: AuthUser | null;
  }
}
