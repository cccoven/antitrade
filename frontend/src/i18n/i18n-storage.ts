export type LanguageMode = "system" | "zh" | "en";
export type ResolvedLanguage = "zh" | "en";

const LANGUAGE_MODE_KEY = "antitrade.languageMode";

export const DEFAULT_LANGUAGE_MODE: LanguageMode = "system";

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function readLanguageMode(): LanguageMode {
  if (!canUseStorage()) return DEFAULT_LANGUAGE_MODE;
  const value = window.localStorage.getItem(LANGUAGE_MODE_KEY);
  return value === "system" || value === "zh" || value === "en"
    ? value
    : DEFAULT_LANGUAGE_MODE;
}

export function writeLanguageMode(mode: LanguageMode) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(LANGUAGE_MODE_KEY, mode);
}
