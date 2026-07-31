import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import i18n from "./index";
import {
  DEFAULT_LANGUAGE_MODE,
  readLanguageMode,
  writeLanguageMode,
  type LanguageMode,
  type ResolvedLanguage,
} from "./i18n-storage";

interface I18nContextValue {
  languageMode: LanguageMode;
  resolvedLanguage: ResolvedLanguage;
  tradingViewLocale: "zh_CN" | "en";
  setLanguageMode: (mode: LanguageMode) => void;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function getSystemLanguage(): ResolvedLanguage {
  if (typeof navigator === "undefined") return "zh";
  const source = navigator.languages?.[0] ?? navigator.language ?? "zh-CN";
  return source.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function resolveLanguage(mode: LanguageMode, systemLanguage: ResolvedLanguage) {
  return mode === "system" ? systemLanguage : mode;
}

function applyLanguageToRoot(language: ResolvedLanguage) {
  if (typeof document === "undefined") return;
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [languageMode, setLanguageModeState] = useState<LanguageMode>(DEFAULT_LANGUAGE_MODE);
  const [systemLanguage, setSystemLanguage] = useState<ResolvedLanguage>("zh");

  useEffect(() => {
    setLanguageModeState(readLanguageMode());
    setSystemLanguage(getSystemLanguage());
  }, []);

  useEffect(() => {
    const update = () => setSystemLanguage(getSystemLanguage());
    window.addEventListener("languagechange", update);
    return () => window.removeEventListener("languagechange", update);
  }, []);

  const resolvedLanguage = resolveLanguage(languageMode, systemLanguage);

  useEffect(() => {
    applyLanguageToRoot(resolvedLanguage);
    void i18n.changeLanguage(resolvedLanguage);
  }, [resolvedLanguage]);

  const value = useMemo<I18nContextValue>(
    () => ({
      languageMode,
      resolvedLanguage,
      tradingViewLocale: resolvedLanguage === "zh" ? "zh_CN" : "en",
      setLanguageMode: (mode) => {
        setLanguageModeState(mode);
        writeLanguageMode(mode);
      },
    }),
    [languageMode, resolvedLanguage]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return context;
}
