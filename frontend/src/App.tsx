import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { BrowserRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Toaster, toast } from "sonner";
import { AuthProvider, useAuth } from "@/auth/AuthProvider";
import { becomePromoter } from "@/auth/becomePromoter";
import { takeDestination, takePromoterOrg } from "@/auth/postAuth";
import { IconSprite } from "@/components/IconSprite";
import { LanguageProvider } from "@/i18n/useTranslation";
import Account from "@/pages/Account";
import Auth from "@/pages/Auth";
import Chat from "@/pages/Chat";
import NotFound from "@/pages/NotFound";
import ProSubmit from "@/pages/ProSubmit";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

/**
 * OAuth comes back to whichever URL Supabase's allow-list permitted, which is
 * not necessarily where the promoter started. Once a session exists, honour
 * what they left with — the destination, and for the promoter's door the
 * organisation, since there was no session to write it into on the way out.
 * Both are spent once, and the destination only if we are not already on it.
 *
 * Renders nothing; it exists to be inside the router, where `navigate` works.
 */
function PostAuthLanding() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => {
    if (isLoading || !user) return;
    const destination = takeDestination();
    const orgName = takePromoterOrg();

    // Before navigating: /pro reads the role off the token, and becomePromoter
    // is what re-mints it. Landing there first would show the refusal screen to
    // someone who is about to become a promoter, then flip under them.
    const run = async () => {
      if (orgName) {
        try {
          await becomePromoter(user.id, orgName);
        } catch {
          // The account is real and signed in either way — say so and let them
          // finish on /account rather than stranding them on a refusal.
          toast.error("Could not finish promoter setup — add it in your account.");
        }
      }
      if (destination && destination !== pathname) navigate(destination, { replace: true });
    };
    void run();
    // pathname is read, not tracked: re-running on navigation would re-enter
    // with both stashes already spent, and only risks a second navigate.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, user, navigate]);

  return null;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* Mounted above everything and never unmounted: every <Icon> is a
          same-document reference into these symbols. */}
      <IconSprite />
      <LanguageProvider>
        <AuthProvider>
          {/* Nothing is square: the toast is a sheet, 26px, on the app ground. */}
          <Toaster
            theme="dark"
            position="top-center"
            richColors
            toastOptions={{
              // Radius and type only — richColors owns the fill, and red is
              // the one colour an error is allowed.
              className: "!rounded-[26px] !font-sans !text-[13.5px]",
            }}
          />
          <BrowserRouter
            future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
          >
            <PostAuthLanding />
            <Routes>
              <Route path="/" element={<Chat />} />
              <Route path="/auth" element={<Auth />} />
              <Route path="/account" element={<Account />} />
              <Route path="/pro" element={<ProSubmit />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </LanguageProvider>
    </QueryClientProvider>
  );
}
