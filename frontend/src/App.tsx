import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LanguageProvider } from "@/hooks/useTranslation";
import { AuthProvider } from "@/hooks/useAuth";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import Chat from "./pages/Chat";
import Auth from "./pages/Auth";
import Promoters from "./pages/Promoters";
import PromoterCreate from "./pages/PromoterCreate";
import PromoterAbout from "./pages/PromoterAbout";
import PromoterAuth from "./pages/PromoterAuth";
import PrintableFlyer from "./pages/PrintableFlyer";
import AccountSettings from "./pages/AccountSettings";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <LanguageProvider>
        <AuthProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Chat />} />
              <Route path="/auth" element={<Auth />} />
              <Route
                path="/account/settings"
                element={
                  <ProtectedRoute>
                    <AccountSettings />
                  </ProtectedRoute>
                }
              />
              <Route path="/promoters" element={<Promoters />} />
              <Route path="/promoters/auth" element={<PromoterAuth />} />
              <Route
                path="/promoters/create"
                element={
                  <ProtectedRoute requirePromoter redirectTo="/promoters/auth">
                    <PromoterCreate />
                  </ProtectedRoute>
                }
              />
              <Route path="/promoters/about" element={<PromoterAbout />} />
              <Route path="/printable-flyer" element={<PrintableFlyer />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </LanguageProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
