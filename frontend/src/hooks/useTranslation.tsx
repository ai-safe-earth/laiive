import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { translations, Language, Translations } from '@/translations';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: Translations;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const STORAGE_KEY = 'laiive-language';

const detectBrowserLanguage = (): Language => {
  const browserLang = navigator.language.split('-')[0];
  const supportedLanguages: Language[] = ['en', 'es', 'it', 'ca'];

  if (supportedLanguages.includes(browserLang as Language)) {
    return browserLang as Language;
  }

  return 'en'; // Default to English
};

export const LanguageProvider = ({ children }: { children: ReactNode }) => {
  const [language, setLanguageState] = useState<Language>(() => {
    // Try to get from localStorage first
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && ['en', 'es', 'it', 'ca'].includes(stored)) {
      return stored as Language;
    }
    // Otherwise detect from browser
    return detectBrowserLanguage();
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, language);
  }, [language]);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
  };

  const t = translations[language];

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useTranslation = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useTranslation must be used within a LanguageProvider');
  }
  return context;
};
