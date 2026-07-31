import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  createBillingCheckout,
  createBillingPortal,
  fetchBillingSummary,
  type BillingFeature,
  type BillingSummary,
} from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import { openExternal } from "@/lib/open-external";
import { isTauriShell } from "@/lib/window-chrome";

interface BillingContextValue {
  summary: BillingSummary | null;
  loading: boolean;
  upgradeOpen: boolean;
  upgradeFeature: BillingFeature | null;
  canUse: (feature: BillingFeature) => boolean;
  refresh: () => Promise<BillingSummary | null>;
  openUpgrade: (feature?: BillingFeature) => void;
  closeUpgrade: () => void;
  startCheckout: (interval: "month" | "year") => Promise<void>;
  manageBilling: () => Promise<void>;
}

const BillingContext = createContext<BillingContextValue | null>(null);

function isBillingFeature(value: unknown): value is BillingFeature {
  return typeof value === "string" && [
    "assistant.basic",
    "assistant.research",
    "assistant.web_search",
    "assistant.vision",
    "assistant.optimize",
    "analysis.run",
    "journal.ai_assist",
    "recognition.parse",
  ].includes(value);
}

async function navigateToStripe(url: string): Promise<void> {
  if (isTauriShell()) {
    await openExternal(url);
    return;
  }
  window.location.assign(url);
}

export function BillingProvider({ children }: { children: ReactNode }) {
  const { user, setLoginDialogOpen } = useAuth();
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [upgradeFeature, setUpgradeFeature] = useState<BillingFeature | null>(null);

  const refresh = useCallback(async () => {
    if (!user) {
      setSummary(null);
      return null;
    }
    setLoading(true);
    try {
      const next = await fetchBillingSummary();
      setSummary(next);
      return next;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!user) return;
    const handleFocus = () => { void refresh(); };
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [refresh, user]);

  useEffect(() => {
    const handleRequired = (event: Event) => {
      const feature = (event as CustomEvent<{ feature?: unknown }>).detail?.feature;
      setUpgradeFeature(isBillingFeature(feature) ? feature : null);
      setUpgradeOpen(true);
      void refresh();
    };
    window.addEventListener("billing:upgrade-required", handleRequired);
    return () => window.removeEventListener("billing:upgrade-required", handleRequired);
  }, [refresh]);

  const openUpgrade = useCallback((feature?: BillingFeature) => {
    if (!user) {
      setLoginDialogOpen(true);
      return;
    }
    setUpgradeFeature(feature ?? null);
    setUpgradeOpen(true);
  }, [setLoginDialogOpen, user]);

  const closeUpgrade = useCallback(() => setUpgradeOpen(false), []);

  const startCheckout = useCallback(async (interval: "month" | "year") => {
    const result = await createBillingCheckout(interval);
    await navigateToStripe(result.url);
  }, []);

  const manageBilling = useCallback(async () => {
    const result = await createBillingPortal();
    await navigateToStripe(result.url);
  }, []);

  const value = useMemo<BillingContextValue>(() => ({
    summary,
    loading,
    upgradeOpen,
    upgradeFeature,
    // While an authenticated user's summary is loading, let the request reach
    // the authoritative backend gate instead of briefly treating Pro as Free.
    canUse: (feature) => Boolean(user && (!summary || summary.features[feature])),
    refresh,
    openUpgrade,
    closeUpgrade,
    startCheckout,
    manageBilling,
  }), [
    closeUpgrade,
    loading,
    manageBilling,
    openUpgrade,
    refresh,
    startCheckout,
    summary,
    upgradeFeature,
    upgradeOpen,
    user,
  ]);

  return <BillingContext.Provider value={value}>{children}</BillingContext.Provider>;
}

export function useBilling() {
  const context = useContext(BillingContext);
  if (!context) throw new Error("useBilling must be used within BillingProvider");
  return context;
}
