import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";
import {
  fetchJournalSettings,
  updateJournalSettings,
  type JournalCurrencyCode,
  type JournalSettings,
} from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import {
  formatJournalMoney,
  maskJournalMoney,
} from "@/journal/journal-currency";
import {
  readJournalAmountsVisible,
  writeJournalAmountsVisible,
} from "@/state/ui-storage";

interface JournalSettingsContextValue {
  startingCapital: number | null | undefined;
  currencyCode: JournalCurrencyCode | null;
  loading: boolean;
  loaded: boolean;
  amountsVisible: boolean;
  setStartingCapital: (value: number | null) => Promise<void>;
  setCurrencyCode: (value: JournalCurrencyCode) => Promise<void>;
  setAmountsVisible: (value: boolean) => void;
  formatMoney: (
    value: number | null | undefined,
    options?: { signed?: boolean },
  ) => string;
  displayMoney: (
    value: number | null | undefined,
    options?: { signed?: boolean },
  ) => string;
}

const JournalSettingsContext = createContext<JournalSettingsContextValue | null>(null);

export function JournalSettingsProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const { i18n } = useTranslation();
  const [settings, setSettings] = useState<JournalSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [amountsVisible, setAmountsVisibleState] = useState(() =>
    readJournalAmountsVisible(true),
  );

  useEffect(() => {
    let cancelled = false;
    setSettings(null);
    if (authLoading || !user) {
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);
    fetchJournalSettings()
      .then((next) => {
        if (!cancelled) setSettings(next);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [authLoading, user]);

  const update = useCallback(async (patch: Partial<JournalSettings>) => {
    const next = await updateJournalSettings(patch);
    setSettings(next);
  }, []);

  const setStartingCapital = useCallback(
    (value: number | null) => update({ starting_capital: value }),
    [update],
  );

  const setCurrencyCode = useCallback(
    (value: JournalCurrencyCode) => update({ currency_code: value }),
    [update],
  );

  const setAmountsVisible = useCallback((value: boolean) => {
    setAmountsVisibleState(value);
    writeJournalAmountsVisible(value);
  }, []);

  const formatMoney = useCallback(
    (value: number | null | undefined, options?: { signed?: boolean }) =>
      formatJournalMoney(value, settings?.currency_code ?? null, i18n.language, options),
    [i18n.language, settings?.currency_code],
  );

  const displayMoney = useCallback(
    (value: number | null | undefined, options?: { signed?: boolean }) =>
      maskJournalMoney(value, formatMoney(value, options), amountsVisible),
    [amountsVisible, formatMoney],
  );

  const value = useMemo<JournalSettingsContextValue>(() => ({
    startingCapital: settings ? settings.starting_capital : undefined,
    currencyCode: settings?.currency_code ?? null,
    loading,
    loaded: settings != null,
    amountsVisible,
    setStartingCapital,
    setCurrencyCode,
    setAmountsVisible,
    formatMoney,
    displayMoney,
  }), [
    amountsVisible,
    displayMoney,
    formatMoney,
    loading,
    setAmountsVisible,
    setCurrencyCode,
    setStartingCapital,
    settings,
  ]);

  return (
    <JournalSettingsContext.Provider value={value}>
      {children}
    </JournalSettingsContext.Provider>
  );
}

export function useJournalSettings(): JournalSettingsContextValue {
  const context = useContext(JournalSettingsContext);
  if (!context) {
    throw new Error("useJournalSettings must be used within JournalSettingsProvider");
  }
  return context;
}
