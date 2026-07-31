import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useState,
} from "react";
import type { ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle,
  ArrowLeft,
  Clock3,
  Database,
  Gauge,
  LogIn,
  LogOut,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import FlushPage from "@/components/FlushPage";
import ReplayChart from "@/components/ReplayChart";
import ReplayControls from "@/components/ReplayControls";
import {
  fetchReplayBundle,
  ReplayApiError,
  type ReplayApiProblem,
  type ReplayBundle,
} from "@/api/client";
import {
  createReplayPlaybackState,
  replayPlaybackReducer,
  type ReplaySpeed,
} from "@/pages/replay-machine";
import { calculateReplayExcursion } from "@/pages/replay-metrics";
import {
  REPLAY_PREFS_STORAGE_KEY,
  replayPageStyles,
} from "@/pages/replay-ui-config";

type WindowPreset = "compact" | "standard" | "full";

interface ReplayPrefs {
  interval: string;
  window: WindowPreset;
  speed: ReplaySpeed;
}

const DEFAULT_PREFS: ReplayPrefs = {
  interval: "auto",
  window: "standard",
  speed: 1,
};

function readPrefs(): ReplayPrefs {
  try {
    const raw = localStorage.getItem(REPLAY_PREFS_STORAGE_KEY);
    if (!raw) return DEFAULT_PREFS;
    const parsed = JSON.parse(raw);
    return {
      interval:
        typeof parsed.interval === "string"
          ? parsed.interval
          : DEFAULT_PREFS.interval,
      window: ["compact", "standard", "full"].includes(parsed.window)
        ? parsed.window
        : DEFAULT_PREFS.window,
      speed: [0.5, 1, 2, 4].includes(parsed.speed)
        ? parsed.speed
        : DEFAULT_PREFS.speed,
    };
  } catch {
    return DEFAULT_PREFS;
  }
}

function writePrefs(prefs: ReplayPrefs) {
  try {
    localStorage.setItem(REPLAY_PREFS_STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // Browser persistence is optional.
  }
}

export default function ReplayPage() {
  const { tradeId } = useParams<{ tradeId: string }>();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();

  const initialPrefs = useMemo(readPrefs, []);
  const [interval, setInterval] = useState(initialPrefs.interval);
  const [windowPreset, setWindowPreset] = useState<WindowPreset>(
    initialPrefs.window,
  );
  const [bundle, setBundle] = useState<ReplayBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ReplayApiProblem | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [playback, dispatch] = useReducer(
    replayPlaybackReducer,
    createReplayPlaybackState({
      startCursor: 1,
      decisionCursor: 1,
      totalBars: 1,
      speed: initialPrefs.speed,
    }),
  );

  useEffect(() => {
    writePrefs({
      interval,
      window: windowPreset,
      speed: playback.speed,
    });
  }, [interval, playback.speed, windowPreset]);

  useEffect(() => {
    if (!tradeId) return;
    let cancelled = false;
    setLoading(true);
    setProblem(null);
    setBundle(null);

    fetchReplayBundle(tradeId, {
      interval,
      window: windowPreset,
    })
      .then((nextBundle) => {
        if (cancelled) return;
        setBundle(nextBundle);
        dispatch({
          type: "RESET",
          startCursor: nextBundle.meta.start_index,
          decisionCursor: nextBundle.meta.decision_index,
          totalBars: nextBundle.bars.length,
          speed: playback.speed,
        });
      })
      .catch((error) => {
        if (cancelled) return;
        setProblem(
          error instanceof ReplayApiError
            ? error.problem
            : {
                problem: "unknown",
                retryable: true,
                suggested_intervals: [],
              },
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // playback.speed is intentionally captured only when a new session loads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interval, refreshKey, tradeId, windowPreset]);

  useEffect(() => {
    if (playback.status !== "playing") return;
    const timer = window.setInterval(
      () => dispatch({ type: "TICK" }),
      Math.max(50, 1000 / playback.speed),
    );
    return () => window.clearInterval(timer);
  }, [playback.speed, playback.status]);

  const handleTogglePlay = useCallback(() => {
    dispatch({ type: playback.status === "playing" ? "PAUSE" : "PLAY" });
  }, [playback.status]);

  const currentIndex = bundle
    ? Math.max(0, Math.min(playback.cursor - 1, bundle.bars.length - 1))
    : 0;
  const currentBar = bundle?.bars[currentIndex] ?? null;
  const entryRevealed = !!bundle && playback.cursor > bundle.open_index;
  const exitRevealed =
    !!bundle &&
    bundle.close_index != null &&
    playback.cursor > bundle.close_index;

  const phase = !bundle
    ? "loading"
    : !entryRevealed
      ? "context"
      : exitRevealed
        ? "afterExit"
        : "inPosition";

  const excursion = useMemo(() => {
    if (!bundle || !entryRevealed || bundle.trade.open_price == null) {
      return null;
    }
    const heldEnd =
      bundle.close_index != null && exitRevealed
        ? bundle.close_index
        : currentIndex;
    return calculateReplayExcursion({
      bars: bundle.bars,
      openIndex: bundle.open_index,
      heldEndIndex: heldEnd,
      openPrice: bundle.trade.open_price,
      direction: bundle.trade.direction,
    });
  }, [bundle, currentIndex, entryRevealed, exitRevealed]);

  const progress = bundle
    ? Math.round((playback.cursor / bundle.bars.length) * 100)
    : 0;
  const formatTime = useCallback(
    (seconds: number) =>
      new Intl.DateTimeFormat(i18n.resolvedLanguage ?? "zh", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(seconds * 1000)),
    [i18n.resolvedLanguage],
  );

  const retry = useCallback(() => setRefreshKey((key) => key + 1), []);

  return (
    <FlushPage
      contentClassName="gap-2 pt-3"
      toolbar={
        <div className="flex min-w-0 items-center gap-2">
          <TooltipIconButton
            label={t("replay.back")}
            variant="outline"
            size="icon-sm"
            onClick={() => navigate(-1)}
          >
            <ArrowLeft />
          </TooltipIconButton>
          <span className="truncate text-subheading">
            {bundle ? bundle.trade.symbol : t("replay.title")}
          </span>
          {bundle && (
            <>
              <Badge variant="outline">
                {formatReplayInterval(bundle.meta.interval)}
              </Badge>
              <Badge variant="secondary">
                {bundle.meta.data_source}
              </Badge>
              {bundle.meta.requested_interval === "auto" && (
                <span className="text-caption text-muted-foreground">
                  {t("replay.autoResolved")}
                </span>
              )}
            </>
          )}
        </div>
      }
    >
      <Card className="gap-0 py-0">
        <CardContent className="flex flex-col gap-3 px-3 py-3">
          <ReplayControls
            disabled={!bundle || loading}
            isPlaying={playback.status === "playing"}
            onTogglePlay={handleTogglePlay}
            onPrevBar={() => dispatch({ type: "STEP", delta: -1 })}
            onNextBar={() => dispatch({ type: "STEP", delta: 1 })}
            onJumpToEntry={() => {
              if (bundle) {
                dispatch({ type: "SEEK", cursor: bundle.open_index + 1 });
              }
            }}
            onJumpToExit={() => {
              if (bundle?.close_index != null) {
                dispatch({ type: "SEEK", cursor: bundle.close_index + 1 });
              }
            }}
            onJumpToEnd={() => {
              if (bundle) {
                dispatch({ type: "SEEK", cursor: bundle.bars.length });
              }
            }}
            hasExit={bundle?.close_index != null}
            speed={playback.speed}
            onSpeedChange={(speed) =>
              dispatch({ type: "SET_SPEED", speed: speed as ReplaySpeed })
            }
            interval={interval}
            onIntervalChange={setInterval}
            window={windowPreset}
            onWindowChange={setWindowPreset}
            dataSource={bundle?.meta.data_source ?? null}
          />

          <div className="grid min-h-[520px] overflow-hidden rounded-md border border-border bg-background lg:grid-cols-[minmax(0,1fr)_240px]">
            <div className="relative min-h-[440px]">
              {loading && (
                <div
                  className="flex h-full items-center justify-center text-muted-foreground"
                  style={replayPageStyles.btnStyle}
                >
                  {t("replay.loading")}
                </div>
              )}

              {!loading && problem && (
                <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
                  <span className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
                    <AlertTriangle className="size-[var(--icon-lg)]" />
                  </span>
                  <div className="space-y-1">
                    <div className="text-subheading">
                      {t(`replay.problem.${problem.problem}`)}
                    </div>
                    <div className="max-w-[460px] text-caption text-muted-foreground">
                      {t(`replay.problemHelp.${problem.problem}`)}
                    </div>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2">
                    {problem.suggested_intervals.map((suggested) => (
                      <Button
                        key={suggested}
                        variant="outline"
                        size="sm"
                        style={replayPageStyles.btnStyle}
                        onClick={() => setInterval(suggested)}
                      >
                        {t("replay.tryInterval", { interval: suggested })}
                      </Button>
                    ))}
                    {problem.problem === "instrument_required" ||
                    problem.problem === "missing_open_time" ? (
                      <Button
                        size="sm"
                        style={replayPageStyles.btnStyle}
                        onClick={() => navigate("/journal")}
                      >
                        {t("replay.repairTrade")}
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        style={replayPageStyles.btnStyle}
                        onClick={retry}
                      >
                        {t("replay.retry")}
                      </Button>
                    )}
                  </div>
                </div>
              )}

              {!loading && !problem && bundle && (
                <ReplayChart
                  bars={bundle.bars}
                  visibleCount={playback.cursor}
                  openIndex={bundle.open_index}
                  closeIndex={bundle.close_index}
                  autoFollow={playback.status === "playing"}
                  trade={{
                    direction: bundle.trade.direction,
                    open_price: bundle.trade.open_price,
                    close_price: bundle.trade.close_price,
                  }}
                />
              )}
            </div>

            <aside className="flex flex-col border-t border-border bg-card/40 p-3 lg:border-l lg:border-t-0">
              {bundle ? (
                <div className="flex flex-col gap-4">
                  <div>
                    <div className="text-caption text-muted-foreground">
                      {t("replay.currentPhase")}
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-ui font-medium">
                      <Target className="size-[var(--icon-sm)] text-primary" />
                      {t(`replay.phase.${phase}`)}
                    </div>
                  </div>

                  <ReplayFact
                    icon={<LogIn />}
                    label={t("replay.recordedEntry")}
                    value={`${bundle.trade.open_price == null ? "—" : formatPrice(bundle.trade.open_price)} · ${formatTime(
                      Math.floor(
                        new Date(bundle.trade.open_time).getTime() / 1000,
                      ),
                    )}`}
                    wrap
                  />
                  {bundle.trade.close_time && (
                    <ReplayFact
                      icon={<LogOut />}
                      label={t("replay.recordedExit")}
                      value={`${bundle.trade.close_price == null ? "—" : formatPrice(bundle.trade.close_price)} · ${formatTime(
                        Math.floor(
                          new Date(bundle.trade.close_time).getTime() / 1000,
                        ),
                      )}`}
                      wrap
                    />
                  )}
                  <ReplayFact
                    icon={<Clock3 />}
                    label={t("replay.currentBar")}
                    value={currentBar ? formatTime(currentBar.time) : "—"}
                  />
                  <ReplayFact
                    icon={<Gauge />}
                    label={t("replay.currentPrice")}
                    value={currentBar ? formatPrice(currentBar.close) : "—"}
                  />
                  <ReplayFact
                    icon={<TrendingUp />}
                    label={t("replay.mfeLabel")}
                    value={excursion ? formatSigned(excursion.mfe) : "—"}
                    tone="positive"
                  />
                  <ReplayFact
                    icon={<TrendingDown />}
                    label={t("replay.maeLabel")}
                    value={excursion ? formatSigned(excursion.mae) : "—"}
                    tone="negative"
                  />
                  <ReplayFact
                    icon={<Database />}
                    label={t("replay.coverage")}
                    value={`${formatTime(
                      Math.floor(
                        new Date(bundle.meta.coverage_start).getTime() / 1000,
                      ),
                    )} — ${formatTime(
                      Math.floor(
                        new Date(bundle.meta.coverage_end).getTime() / 1000,
                      ),
                    )}`}
                    wrap
                  />
                </div>
              ) : (
                <div className="text-caption text-muted-foreground">
                  {t("replay.sessionPending")}
                </div>
              )}
            </aside>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative h-6 flex-1">
              <div className="pointer-events-none absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 overflow-hidden rounded-full bg-muted">
                <div
                  className="absolute inset-y-0 left-0 bg-primary transition-[width] duration-150"
                  style={{ width: `${progress}%` }}
                />
              </div>
              {bundle && (
                <>
                  <TimelineMarker
                    position={(bundle.open_index / bundle.bars.length) * 100}
                    label={t("replay.entryMarker")}
                  />
                  {bundle.close_index != null && (
                    <TimelineMarker
                      position={
                        (bundle.close_index / bundle.bars.length) * 100
                      }
                      label={t("replay.exitMarker")}
                    />
                  )}
                </>
              )}
              <input
                aria-label={t("replay.timeline")}
                type="range"
                min={1}
                max={bundle?.bars.length ?? 1}
                value={bundle ? playback.cursor : 1}
                disabled={!bundle || loading}
                onInput={(event) =>
                  dispatch({
                    type: "SEEK",
                    cursor: Number(event.currentTarget.value),
                  })
                }
                className="absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
                style={{ fontSize: "var(--font-ui)" }}
              />
            </div>
            <span className="w-20 text-right text-caption tabular-nums text-muted-foreground">
              {bundle
                ? `${playback.cursor} / ${bundle.bars.length}`
                : "—"}
            </span>
          </div>
        </CardContent>
      </Card>
    </FlushPage>
  );
}

function ReplayFact({
  icon,
  label,
  value,
  tone,
  wrap = false,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone?: "positive" | "negative";
  wrap?: boolean;
}) {
  return (
    <div className="flex gap-2">
      <span className="mt-0.5 text-muted-foreground [&>svg]:size-[var(--icon-sm)]">
        {icon}
      </span>
      <div className="min-w-0">
        <div className="text-caption text-muted-foreground">{label}</div>
        <div
          className={
            tone === "positive"
              ? `${wrap ? "" : "truncate "}text-ui font-medium text-[var(--success)]`
              : tone === "negative"
                ? `${wrap ? "" : "truncate "}text-ui font-medium text-[var(--danger)]`
                : `${wrap ? "" : "truncate "}text-ui font-medium text-foreground`
          }
          title={value}
        >
          {value}
        </div>
      </div>
    </div>
  );
}

function TimelineMarker({
  position,
  label,
}: {
  position: number;
  label: string;
}) {
  return (
    <span
      className="absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-background bg-foreground"
      style={{ left: `${position}%` }}
      title={label}
    />
  );
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 4,
  }).format(value);
}

function formatReplayInterval(interval: string): string {
  if (/^\d+$/.test(interval)) return `${interval}m`;
  return interval;
}

function formatSigned(value: number): string {
  if (Object.is(value, -0) || value === 0) return "0";
  const formatted = new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 4,
    signDisplay: "always",
  }).format(value);
  return formatted;
}
