import { useCallback, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink, useParams } from "react-router-dom";

import { fetchJournalSettings, fetchTradeStats } from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import FlushPage from "@/components/FlushPage";
import { animatedLineTabClassName } from "@/components/ui/tabs";
import { showToast } from "@/components/Toast";
import MarketHoursTool from "@/pages/MarketHoursPage";
import CostImpactTool from "@/pages/trading-tools/CostImpactTool";
import DrawdownTool from "@/pages/trading-tools/DrawdownTool";
import ExpectancyTool from "@/pages/trading-tools/ExpectancyTool";
import MonteCarloTool from "@/pages/trading-tools/MonteCarloTool";
import PositionSizeTool from "@/pages/trading-tools/PositionSizeTool";
import { tradingToolsControlSizes } from "@/pages/trading-tools-ui-config";
import type { JournalToolData } from "@/pages/trading-tools/shared";

const tools = [
  { slug: "clock", labelKey: "tradingTools.tab.clock" },
  { slug: "position", labelKey: "tradingTools.tab.position" },
  { slug: "expectancy", labelKey: "tradingTools.tab.expectancy" },
  { slug: "drawdown", labelKey: "tradingTools.tab.drawdown" },
  { slug: "monte-carlo", labelKey: "tradingTools.tab.monteCarlo" },
  { slug: "cost", labelKey: "tradingTools.tab.cost" },
] as const;

type ToolSlug = (typeof tools)[number]["slug"];

function isToolSlug(value: string | undefined): value is ToolSlug {
  return tools.some((tool) => tool.slug === value);
}

export default function TradingToolsPage() {
  const { t } = useTranslation();
  const { tool } = useParams();
  const { user, setLoginDialogOpen } = useAuth();
  const cache = useRef<JournalToolData | null>(null);

  useEffect(() => {
    cache.current = null;
  }, [user?.id]);

  const loadMyData = useCallback(async (): Promise<JournalToolData | null> => {
    if (!user) {
      setLoginDialogOpen(true);
      return null;
    }
    if (cache.current) return cache.current;
    const [stats, settings] = await Promise.all([fetchTradeStats(), fetchJournalSettings()]);
    if (stats.total_trades === 0) {
      showToast(t("tradingTools.noJournalData"));
    }
    cache.current = { stats, startingCapital: settings.starting_capital };
    return cache.current;
  }, [setLoginDialogOpen, t, user]);

  if (!isToolSlug(tool)) {
    return <Navigate to="/tools/clock" replace />;
  }

  const calculatorTool = tool === "position"
    ? <PositionSizeTool loadMyData={loadMyData} />
    : tool === "expectancy"
      ? <ExpectancyTool loadMyData={loadMyData} />
      : tool === "drawdown"
        ? <DrawdownTool loadMyData={loadMyData} />
        : tool === "monte-carlo"
          ? <MonteCarloTool loadMyData={loadMyData} />
          : tool === "cost"
            ? <CostImpactTool loadMyData={loadMyData} />
            : null;

  return (
    <FlushPage
      toolbar={
        <div className="w-full overflow-x-auto">
          <nav className="flex h-7 min-w-max gap-3" aria-label={t("tradingTools.title")}>
            {tools.map((item) => (
              <NavLink
                key={item.slug}
                to={`/tools/${item.slug}`}
                style={tradingToolsControlSizes.tabStyle}
                className={animatedLineTabClassName}
              >
                {t(item.labelKey)}
              </NavLink>
            ))}
          </nav>
        </div>
      }
      contentClassName="gap-0 px-0 pt-0 pb-0"
    >
      {tool === "clock" ? <MarketHoursTool /> : null}
      {calculatorTool ? <div className="px-4 pt-2 pb-6 lg:px-6">{calculatorTool}</div> : null}
    </FlushPage>
  );
}
