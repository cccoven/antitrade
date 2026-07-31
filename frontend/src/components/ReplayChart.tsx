import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
  type UTCTimestamp,
  type TickMarkType,
  type Time,
} from "lightweight-charts";
import type { ReplayBar } from "@/api/client";
import {
  formatReplayChartTick,
  formatReplayChartTime,
} from "@/components/replay-chart-format";

interface ReplayChartProps {
  bars: ReplayBar[];
  visibleCount: number;
  openIndex: number;
  closeIndex: number | null;
  autoFollow: boolean;
  trade: {
    direction: "long" | "short";
    open_price: number | null;
    close_price: number | null;
  };
}

export default function ReplayChart({
  bars,
  visibleCount,
  openIndex,
  closeIndex,
  autoFollow,
  trade,
}: ReplayChartProps) {
  const { t, i18n } = useTranslation();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const entryLineRef = useRef<IPriceLine | null>(null);
  const exitLineRef = useRef<IPriceLine | null>(null);
  const previousVisibleCountRef = useRef(0);
  const previousBarsRef = useRef<ReplayBar[] | null>(null);
  const locale = i18n.resolvedLanguage ?? "zh-CN";
  const timeZone = useMemo(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone,
    [],
  );

  // Mount/unmount the chart
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { color: "transparent" },
        textColor:
          getComputedStyle(document.documentElement)
            .getPropertyValue("--foreground")
            .trim() || "#aaa",
      },
      grid: {
        vertLines: { color: "rgba(120,120,120,0.08)" },
        horzLines: { color: "rgba(120,120,120,0.08)" },
      },
      localization: {
        locale,
        timeFormatter: (time: Time) =>
          formatReplayChartTime(time, locale, timeZone),
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: Time, tickMarkType: TickMarkType) =>
          formatReplayChartTick(time, tickMarkType, locale, timeZone),
      },
      rightPriceScale: { borderVisible: false },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    chartRef.current = chart;
    seriesRef.current = series;
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      entryLineRef.current = null;
      exitLineRef.current = null;
    };
  }, [locale, timeZone]);

  // Update visible bars whenever inputs change
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    const nextVisibleCount = Math.max(
      0,
      Math.min(visibleCount, bars.length),
    );
    const toCandle = (bar: ReplayBar) => ({
      time: bar.time as UTCTimestamp,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    });
    const isNewSession = previousBarsRef.current !== bars;
    const previousVisibleCount = previousVisibleCountRef.current;

    if (
      isNewSession ||
      nextVisibleCount <= previousVisibleCount ||
      nextVisibleCount > previousVisibleCount + 1
    ) {
      series.setData(
        bars.slice(0, nextVisibleCount).map((bar) => toCandle(bar)),
      );
      if (isNewSession) chartRef.current?.timeScale().fitContent();
    } else {
      const nextBar = bars[nextVisibleCount - 1];
      if (nextBar) series.update(toCandle(nextBar));
    }
    previousBarsRef.current = bars;
    previousVisibleCountRef.current = nextVisibleCount;

    if (autoFollow) {
      chartRef.current?.timeScale().scrollToRealTime();
    }

    // Entry priceLine + marker
    if (entryLineRef.current) {
      series.removePriceLine(entryLineRef.current);
      entryLineRef.current = null;
    }
    if (exitLineRef.current) {
      series.removePriceLine(exitLineRef.current);
      exitLineRef.current = null;
    }
    const markers: {
      time: UTCTimestamp;
      position: "aboveBar" | "belowBar";
      color: string;
      shape: "arrowUp" | "arrowDown";
      text: string;
    }[] = [];

    if (visibleCount > openIndex && trade.open_price != null) {
      entryLineRef.current = series.createPriceLine({
        price: trade.open_price,
        color: "rgba(80,80,80,0.85)",
        lineWidth: 1,
        lineStyle: 0,
        axisLabelVisible: true,
        title: t("replay.entryMarker"),
      });
      const bar = bars[openIndex];
      if (bar) {
        markers.push({
          time: bar.time as UTCTimestamp,
          position: trade.direction === "long" ? "belowBar" : "aboveBar",
          color: trade.direction === "long" ? "#22c55e" : "#ef4444",
          shape: trade.direction === "long" ? "arrowUp" : "arrowDown",
          text: t("replay.entryMarker"),
        });
      }
    }

    if (
      closeIndex != null &&
      visibleCount > closeIndex &&
      trade.close_price != null
    ) {
      exitLineRef.current = series.createPriceLine({
        price: trade.close_price,
        color: "#888",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: t("replay.exitMarker"),
      });
      const bar = bars[closeIndex];
      if (bar) {
        markers.push({
          time: bar.time as UTCTimestamp,
          position: trade.direction === "long" ? "aboveBar" : "belowBar",
          color: "#888",
          shape: trade.direction === "long" ? "arrowDown" : "arrowUp",
          text: t("replay.exitMarker"),
        });
      }
    }
    series.setMarkers(markers);
  }, [
    bars,
    visibleCount,
    openIndex,
    closeIndex,
    trade.direction,
    trade.open_price,
    trade.close_price,
    autoFollow,
    t,
  ]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
    </div>
  );
}
