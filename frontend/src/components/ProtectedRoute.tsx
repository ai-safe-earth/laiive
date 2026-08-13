import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

interface ProtectedRouteProps {
  children: ReactNode;
  /** If true, also require the user to have the promoter role */
  requirePromoter?: boolean;
  /** Where to redirect when not authenticated (default: /auth) */
  redirectTo?: string;
}

export function ProtectedRoute({
  children,
  requirePromoter = false,
  redirectTo,
}: ProtectedRouteProps) {
  const { user, isPromoter, isLoading } = useAuth();

  if (isLoading) {
    return null; // or a spinner — keep it minimal
  }

  if (!user) {
    return <Navigate to={redirectTo ?? "/auth"} replace />;
  }

  if (requirePromoter && !isPromoter) {
    return <Navigate to={redirectTo ?? "/promoters/auth"} replace />;
  }

  return <>{children}</>;
}
