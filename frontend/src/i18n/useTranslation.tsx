import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { translations, type Language, type Translations } from "./translations";

const LANGUAGES: readonly Language[] = ["en", "es", "it", "ca"];
const STORAGE_KEY = "laiive-language";

interface LanguageState {
  language: Language;
  setLanguage: (language: Language) => void;
  t: Translations;
}

const LanguageContext = createContext<LanguageState | undefined>(undefined);

function isLanguage(value: string | null): value is Language {
  return value !== null && (LANGUAGES as readonly string[]).includes(value);
}

function initialLanguage(): Language {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (isLanguage(stored)) return stored;
  const browser = navigator.language.split("-")[0] ?? "";
  return isLanguage(browser) ? browser : "en";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(initialLanguage);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, language);
    document.documentElement.lang = language;
  }, [language]);

  const value = useMemo<LanguageState>(
    () => ({ language, setLanguage, t: translations[language] }),
    [language],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useTranslation(): LanguageState {
  const context = useContext(LanguageContext);
  if (!context) throw new Error("useTranslation must be used within a LanguageProvider");
  return context;
}

export { LANGUAGES };
export type { Language };
