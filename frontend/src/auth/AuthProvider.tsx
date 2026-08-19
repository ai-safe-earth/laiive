import type { Session, User } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { roleFromToken, supabase, type UserRole } from "./supabase";

interface AuthState {
  user: User | null;
  session: Session | null;
  role: UserRole;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  /** Absolute URL to return to; defaults to the origin root. */
  signInWithGoogle: (redirectTo?: string) => Promise<void>;
  /** Resolves to whether a session came back — see the implementation. */
  signUp: (email: string, password: string, displayName?: string) => Promise<{ signedIn: boolean }>;
  signOut: () => Promise<void>;
  /** Re-mint the access token so a role granted server-side reaches the client. */
  refreshRole: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Subscribe first, then fetch: a token refresh landing between the two
    // would otherwise be missed and leave the UI on a stale session.
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
      setIsLoading(false);
    });

    supabase.auth.getSession().then(({ data: { session: current } }) => {
      setSession(current);
      setIsLoading(false);
    });

    return () => data.subscription.unsubscribe();
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user: session?.user ?? null,
      session,
      role: roleFromToken(session?.access_token),
      isLoading,
      signIn: async (email, password) => {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw new Error(error.message);
      },
      signInWithGoogle: async (redirectTo) => {
        // Google → Supabase's /auth/v1/callback → back here; detectSessionInUrl
        // picks the session out of the redirect, onAuthStateChange does the rest.
        //
        // Supabase drops a redirectTo its Redirect URLs allow-list does not
        // match and sends the user to the Site URL instead, saying nothing.
        // Callers that care where they land also stash it — auth/postAuth.ts.
        const { error } = await supabase.auth.signInWithOAuth({
          provider: "google",
          options: { redirectTo: redirectTo ?? window.location.origin },
        });
        if (error) throw new Error(error.message);
      },
      signUp: async (email, password, displayName) => {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: displayName ? { display_name: displayName } : undefined },
        });
        if (error) throw new Error(error.message);
        // Whether a confirmation mail is on its way is the project's setting,
        // not the app's, and the only honest signal is what came back: with
        // "Confirm email" off Supabase hands over a live session here, and the
        // caller must not send the user to an inbox nothing was ever sent to.
        return { signedIn: data.session !== null };
      },
      signOut: async () => {
        await supabase.auth.signOut();
      },
      refreshRole: async () => {
        // The role rides in the JWT's user_role claim, stamped at issue by the
        // custom access token hook. A grant that lands server-side is invisible
        // until the token is re-minted — otherwise a promoter who just became
        // one is still refused for up to an hour.
        const { error } = await supabase.auth.refreshSession();
        if (error) throw new Error(error.message);
      },
    }),
    [session, isLoading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
