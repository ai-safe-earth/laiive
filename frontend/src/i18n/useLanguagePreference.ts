/**
 * The language the chrome is in, and where that choice is remembered.
 *
 * Anonymous: localStorage, set from the browser on a first visit.
 * Signed in: `profiles.ui_language` wins, so the choice follows the account to
 * another device. Picking a language writes through to the row.
 *
 * LanguageProvider sits above AuthProvider in App.tsx and knows nothing about
 * sessions; this hook is the seam between the two.
 */
import { useEffect } from "react";
import { useProfile, useUpdateProfile } from "@/api/profile";
import { useAuth } from "@/auth/AuthProvider";
import { useTranslation, type Language } from "./useTranslation";

export function useLanguagePreference() {
  const { user } = useAuth();
  const { language, setLanguage } = useTranslation();
  const { data: profile } = useProfile(user?.id);
  const update = useUpdateProfile(user?.id);

  const stored = profile?.ui_language;
  useEffect(() => {
    // Only reacts to the stored value changing, never to local changes — the
    // write-through below refreshes the row, so the two cannot fight.
    if (stored) setLanguage(stored);
  }, [stored, setLanguage]);

  const chooseLanguage = (next: Language) => {
    setLanguage(next);
    if (user) update.mutate({ ui_language: next });
  };

  return { language, chooseLanguage, isSaving: update.isPending };
}
