import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";
import AppShell from "./components/AppShell";
import MarketOverviewPage from "./pages/MarketOverviewPage";
import { I18nProvider } from "./i18n/i18n-context";
import { ThemeProvider } from "./theme/theme-context";
import { ToastProvider } from "./components/Toast";
import { AuthProvider } from "./auth/auth-context";
import AuthDialog from "./auth/AuthDialog";
import JournalCurrencyPrompt from "./journal/JournalCurrencyPrompt";
import { JournalSettingsProvider } from "./journal/journal-settings-context";
import { BillingProvider } from "./billing/billing-context";
import BillingUpgradeDialog from "./billing/BillingUpgradeDialog";

const JournalPage = lazy(() => import("./pages/JournalPage"));
const DailyReviewPage = lazy(() => import("./pages/DailyReviewPage"));
const BacktestPage = lazy(() => import("./pages/BacktestPage"));
const BacktestResultPage = lazy(() => import("./pages/BacktestResultPage"));
const PortfolioPage = lazy(() => import("./pages/PortfolioPage"));
const ReplayPage = lazy(() => import("./pages/ReplayPage"));
const StrategiesPage = lazy(() => import("./pages/StrategiesPage"));
const StrategyDetailPage = lazy(() => import("./pages/StrategyDetailPage"));
const AssistantPage = lazy(() => import("./pages/AssistantPage"));
const RadarPage = lazy(() => import("./pages/RadarPage"));
const FeedDetailPage = lazy(() => import("./pages/FeedDetailPage"));
const FeedBookmarksPage = lazy(() => import("./pages/FeedBookmarksPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const TradingToolsPage = lazy(() => import("./pages/TradingToolsPage"));
const AutomationsPage = lazy(() => import("./pages/AutomationsPage"));

function RouteLoading() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-40 items-center justify-center text-ui text-muted-foreground">
      {t("common.loading")}
    </div>
  );
}

export default function App() {
  return (
    <I18nProvider>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>
            <BillingProvider>
              <JournalSettingsProvider>
                <BrowserRouter>
                  <div className="app-frame">
                    <AppShell>
                      <Suspense fallback={<RouteLoading />}>
                        <Routes>
                          <Route path="/" element={<MarketOverviewPage />} />
                          <Route path="/tools" element={<Navigate to="/tools/clock" replace />} />
                          <Route path="/tools/:tool" element={<TradingToolsPage />} />
                          <Route path="/assistant" element={<AssistantPage />} />
                          <Route path="/automations" element={<AutomationsPage />} />
                          <Route path="/radar" element={<RadarPage />} />
                          <Route path="/radar/bookmarks" element={<FeedBookmarksPage />} />
                          <Route path="/radar/:id" element={<FeedDetailPage />} />
                          <Route path="/journal" element={<JournalPage />} />
                          <Route path="/journal/review" element={<DailyReviewPage />} />
                          <Route path="/portfolio" element={<PortfolioPage />} />
                          <Route path="/backtest" element={<BacktestPage />} />
                          <Route path="/backtest/runs/:runId" element={<BacktestResultPage />} />
                          <Route path="/replay/:tradeId" element={<ReplayPage />} />
                          <Route path="/strategies" element={<StrategiesPage />} />
                          <Route path="/strategies/:id" element={<StrategyDetailPage />} />
                          <Route path="/settings" element={<SettingsPage />} />
                        </Routes>
                      </Suspense>
                    </AppShell>
                  </div>
                  <JournalCurrencyPrompt />
                  <AuthDialog />
                  <BillingUpgradeDialog />
                </BrowserRouter>
              </JournalSettingsProvider>
            </BillingProvider>
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </I18nProvider>
  );
}
