import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/auth/AuthProvider";
import { LanguageProvider } from "@/i18n/useTranslation";
import Account from "@/pages/Account";
import Auth from "@/pages/Auth";
import Chat from "@/pages/Chat";
import NotFound from "@/pages/NotFound";
import ProSubmit from "@/pages/ProSubmit";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
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
