import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  ACCENT_COLOR_BY_THEME,
  DEFAULT_THEME_MODE,
  readThemeMode,
  writeThemeMode,
  type ResolvedTheme,
  type ThemeMode,
} from "./theme-storage";

interface ThemeContextValue {
  themeMode: ThemeMode;
  resolvedTheme: ResolvedTheme;
  setThemeMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function hexToRgb(hex: string) {
  const normalized = hex.replace("#", "");
  const int = Number.parseInt(normalized, 16);
  return {
    r: (int >> 16) & 255,
    g: (int >> 8) & 255,
    b: int & 255,
  };
}

function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return "light";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyThemeToRoot(theme: ResolvedTheme) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const accentColor = ACCENT_COLOR_BY_THEME[theme];
  const { r, g, b } = hexToRgb(accentColor);
  root.classList.toggle("dark", theme === "dark");
  delete root.dataset.theme;
  root.style.colorScheme = theme;
  root.style.setProperty("--accent", accentColor);
  root.style.setProperty("--accent-rgb", `${r}, ${g}, ${b}`);
  root.style.setProperty("--accent-soft", `rgba(${r}, ${g}, ${b}, 0.12)`);
  root.style.setProperty("--accent-strong", `rgba(${r}, ${g}, ${b}, 0.22)`);
  root.style.setProperty("--accent-ghost", `rgba(${r}, ${g}, ${b}, 0.08)`);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeMode, setThemeModeState] = useState<ThemeMode>(DEFAULT_THEME_MODE);
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>("light");

  useEffect(() => {
    setThemeModeState(readThemeMode());
    setSystemTheme(getSystemTheme());
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setSystemTheme(media.matches ? "dark" : "light");
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  const resolvedTheme = themeMode === "system" ? systemTheme : themeMode;

  useEffect(() => {
    applyThemeToRoot(resolvedTheme);
  }, [resolvedTheme]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      themeMode,
      resolvedTheme,
      setThemeMode: (mode) => {
        setThemeModeState(mode);
        writeThemeMode(mode);
      },
    }),
    [themeMode, resolvedTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}
