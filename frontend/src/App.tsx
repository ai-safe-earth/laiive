import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/auth/AuthProvider";
import { RequireRole } from "@/auth/RequireRole";
import { PostAuthLanding } from "@/auth/PostAuthLanding";
import { CALLBACK_PATH } from "@/auth/postAuth";
import { IconSprite } from "@/components/IconSprite";
import { LanguageProvider } from "@/i18n/useTranslation";
import Account from "@/pages/Account";
import AdminQueue from "@/pages/AdminQueue";
import AdminReport from "@/pages/AdminReport";
import Auth from "@/pages/Auth";
import AuthCallback from "@/pages/AuthCallback";
import Chat from "@/pages/Chat";
import NotFound from "@/pages/NotFound";
import ProSubmit from "@/pages/ProSubmit";
import Saved from "@/pages/Saved";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

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
              <Route path={CALLBACK_PATH} element={<AuthCallback />} />
              <Route path="/account" element={<Account />} />
              <Route path="/pro" element={<ProSubmit />} />
              {/* RequireRole as a sign-in gate rather than a role gate:
                  "user" is the floor, so this refuses nobody who is signed
                  in, and sends anybody else to /auth carrying where they
                  were, so they land back on their list. */}
              <Route
                path="/saved"
                element={
                  <RequireRole minimum="user">
                    <Saved />
                  </RequireRole>
                }
              />
              {/* The role-gated ones. /pro keeps its own
                  refusal screen, which explains how to become a promoter —
                  a redirect would just drop someone on the chat with no clue
                  why. There is nothing to explain about /admin. */}
              <Route
                path="/admin"
                element={
                  <RequireRole minimum="admin">
                    <AdminQueue />
                  </RequireRole>
                }
              />
              <Route
                path="/admin/reports/:id"
                element={
                  <RequireRole minimum="admin">
                    <AdminReport />
                  </RequireRole>
                }
              />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </LanguageProvider>
    </QueryClientProvider>
  );
}
