import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import type { UserRole } from "@/auth/supabase";

/** user < pro < admin — the same order the gateway's requireRole uses. */
const ROLES: readonly UserRole[] = ["user", "pro", "admin"];

/**
 * Gate a route on a minimum role.
 *
 * Two rules the app already learned the hard way and that this keeps in one
 * place. Nothing renders while the session is still loading — a gate that
 * decides before the token has been read shows a refusal to someone who is
 * signed in, and then flips under them. And a signed-in user who simply lacks
 * the role is *not* redirected to /auth, because sending them to a sign-in
 * form they are already past is a dead end; they go where they can act.
 */
export function RequireRole({
  minimum,
  children,
}: {
  minimum: UserRole;
  children: React.ReactNode;
}) {
  const { user, role, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return null;

  if (!user) {
    // `from` lets the sign-in flow return here rather than to the root.
    return <Navigate to="/auth" state={{ from: location.pathname }} replace />;
  }

  // Home, always: every gated route in the app sends a signed-in user who
  // lacks the role to the same place, so there is nothing for a caller to pick.
  if (ROLES.indexOf(role) < ROLES.indexOf(minimum)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
