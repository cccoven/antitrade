export type ThemeMode = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

const THEME_MODE_KEY = "antitrade.themeMode";

export const DEFAULT_THEME_MODE: ThemeMode = "system";

/**
 * Theme-derived accent. Dark mode pulls toward off-white; light mode toward
 * off-black. Both are pulled slightly off pure so cards/borders/hover layers
 * stay readable.
 */
export const ACCENT_COLOR_BY_THEME: Record<ResolvedTheme, string> = {
  dark: "#e6e6e6",
  light: "#1f1f1f",
};

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function readThemeMode(): ThemeMode {
  if (!canUseStorage()) return DEFAULT_THEME_MODE;
  const value = window.localStorage.getItem(THEME_MODE_KEY);
  return value === "light" || value === "dark" || value === "system"
    ? value
    : DEFAULT_THEME_MODE;
}

export function writeThemeMode(mode: ThemeMode) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(THEME_MODE_KEY, mode);
}
