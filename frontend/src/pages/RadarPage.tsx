import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowUp, Bookmark, RefreshCw, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  animatedLineTabClassName,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import FlushPage from "@/components/FlushPage";
import BriefingCard from "@/components/radar/BriefingCard";
import EconomicCalendar, { localDateKey } from "@/components/radar/EconomicCalendar";
import FeedItemCard from "@/components/radar/FeedItemCard";
import { radarControlSizes, RADAR_CATEGORIES, type RadarCategory } from "./radar-ui-config";
import {
  type FeedBriefing, type FeedBookmark, type FeedItem,
  listFeedItems, pollFeedItems, fetchLatestBriefing, listFeedBookmarks,
  addFeedBookmark, removeFeedBookmark, fetchEconomicCalendar,
  type EconomicCalendarData,
} from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import { useI18n } from "@/i18n/i18n-context";

const controlStyle = { fontSize: radarControlSizes.fontSize, fontWeight: radarControlSizes.fontWeight };
const PAGE_SIZE = 20;
const POLL_INTERVAL_MS = 60_000;

export default function RadarPage() {
  const { t } = useTranslation();
  const { resolvedLanguage } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [category, setCategory] = useState<RadarCategory>("all");
  const [activeTab, setActiveTab] = useState("feed");
  const [calendar, setCalendar] = useState<EconomicCalendarData | null>(null);
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState(() => localDateKey(new Date()));
  // `query` tracks the input for instant feedback; `debouncedQuery` trails it
  // and is what actually drives fetching, so typing doesn't fire a request per
  // keystroke.
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [items, setItems] = useState<FeedItem[]>([]);
  const [briefing, setBriefing] = useState<FeedBriefing | null>(null);
  const [bookmarks, setBookmarks] = useState<FeedBookmark[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [feedFailed, setFeedFailed] = useState(false);
  const [newCount, setNewCount] = useState(0);
  const [bannerBox, setBannerBox] = useState<{ top: number; left: number } | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  // Newest item id currently rendered; the poller compares against it to
  // count how many fresh items arrived without disturbing the list.
  const topIdRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setBriefing(null);
    fetchLatestBriefing(resolvedLanguage)
      .then((value) => {
        if (!cancelled) setBriefing(value);
      })
      .catch(() => {
        if (!cancelled) setBriefing(null);
      });
    return () => {
      cancelled = true;
    };
  }, [resolvedLanguage]);

  const loadCalendar = useCallback(() => {
    setCalendarLoading(true);
    fetchEconomicCalendar()
      .then(setCalendar)
      .catch(() => setCalendar({ provider: "forex_factory", items: [], error: "calendar_unavailable" }))
      .finally(() => setCalendarLoading(false));
  }, []);

  useEffect(() => {
    if (activeTab !== "calendar" || calendar) return;
    loadCalendar();
  }, [activeTab, calendar, loadCalendar]);

  // Debounce the search box: only commit the query 350ms after typing stops,
  // so filtering doesn't fire a request on every keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 350);
    return () => clearTimeout(timer);
  }, [query]);

  // Reset + load first page whenever the filter changes.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFeedFailed(false);
    setNewCount(0);
    listFeedItems({
      category: category === "all" ? undefined : category,
      q: debouncedQuery.trim() || undefined,
      lang: resolvedLanguage,
      page: 1,
      page_size: PAGE_SIZE,
    })
      .then((r) => {
        if (cancelled) return;
        setItems(r.items);
        setTotal(r.total);
        setPage(1);
        topIdRef.current = r.items[0]?.id ?? null;
      })
      .catch(() => {
        if (!cancelled) { setItems([]); setTotal(0); setFeedFailed(true); }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [category, debouncedQuery, resolvedLanguage]);

  // Background poll: silently fetch the first page and count how many items
  // are newer than what's on top. Never mutates the list — just surfaces a
  // "N new" banner the user can click to refresh. Paused while a fetch is in
  // flight to avoid racing the filter-change / load-more effects.
  useEffect(() => {
    const timer = setInterval(() => {
      if (loading) return;
      pollFeedItems({
        category: category === "all" ? undefined : category,
        q: debouncedQuery.trim() || undefined,
        lang: resolvedLanguage,
        page: 1,
        page_size: PAGE_SIZE,
      })
        .then((r) => {
          const topId = topIdRef.current;
          if (!topId) { setNewCount(0); return; }
          const idx = r.items.findIndex((it) => it.id === topId);
          // idx === -1 → the whole page turned over (many new items).
          setNewCount(idx === -1 ? r.items.length : idx);
        })
        .catch(() => { /* silent: transient poll failure */ });
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [category, debouncedQuery, loading, resolvedLanguage]);

  // Pull the newest items in and jump to top when the banner is clicked.
  const refreshTop = useCallback(() => {
    setLoading(true);
    setFeedFailed(false);
    setNewCount(0);
    listFeedItems({
      category: category === "all" ? undefined : category,
      q: query.trim() || undefined,
      lang: resolvedLanguage,
      page: 1,
      page_size: PAGE_SIZE,
    })
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
        setPage(1);
        topIdRef.current = r.items[0]?.id ?? null;
        // Scroll the sentinel into view rather than calling scrollTo on a
        // specific element — the actual scroll container is an ancestor of
        // .journal-content (see the banner comment below), so scrollIntoView
        // is container-agnostic and reliably reaches the top.
        scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      })
      .catch(() => setFeedFailed(true))
      .finally(() => setLoading(false));
  }, [category, debouncedQuery, resolvedLanguage]);

  // The banner floats via position:fixed (sticky can't work here — the real
  // scroll container is an ancestor of .journal-content, so a sticky child
  // just scrolls away). Measure the content column + toolbar so the fixed
  // pill stays centered over the feed and pinned just below the toolbar.
  useEffect(() => {
    if (newCount === 0) { setBannerBox(null); return; }
    const measure = () => {
      const content = scrollRef.current?.closest(".journal-content") as HTMLElement | null;
      if (!content) return;
      const rect = content.getBoundingClientRect();
      const strip = content.parentElement?.querySelector(".control-strip-flush");
      const stripBottom = strip ? strip.getBoundingClientRect().bottom : rect.top;
      setBannerBox({ top: stripBottom + 8, left: rect.left + rect.width / 2 });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [newCount]);

  const loadMore = useCallback(() => {
    if (loading || items.length >= total) return;
    const next = page + 1;
    setLoading(true);
    listFeedItems({
      category: category === "all" ? undefined : category,
      q: query.trim() || undefined,
      lang: resolvedLanguage,
      page: next,
      page_size: PAGE_SIZE,
    })
      .then((r) => {
        setItems((cur) => [...cur, ...r.items]);
        setTotal(r.total);
        setPage(next);
      })
      .catch(() => { /* toast handled upstream */ })
      .finally(() => setLoading(false));
  }, [loading, items.length, total, page, category, debouncedQuery, resolvedLanguage]);

  // Infinite scroll: observe a sentinel near the bottom.
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => { if (entries[0]?.isIntersecting) loadMore(); },
      { rootMargin: "400px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [loadMore]);

  useEffect(() => {
    if (!user) {
      setBookmarks([]);
      return;
    }
    listFeedBookmarks().then(setBookmarks).catch(() => setBookmarks([]));
  }, [user]);

  const bookmarkedIds = useMemo(
    () => new Set(bookmarks.map((b) => b.feed_item_id)),
    [bookmarks],
  );
  const sourceCount = useMemo(
    () => new Set(items.map((item) => item.source_key)).size,
    [items],
  );
  const latestItemTime = items[0]?.published_at ?? items[0]?.fetched_at ?? null;

  const handleToggleBookmark = useCallback(async (item: FeedItem) => {
    const existing = bookmarks.find((b) => b.feed_item_id === item.id);
    try {
      if (existing) {
        await removeFeedBookmark(existing.id);
        setBookmarks((cur) => cur.filter((b) => b.id !== existing.id));
      } else {
        const bm = await addFeedBookmark(item.id);
        setBookmarks((cur) => [bm, ...cur]);
      }
    } catch {
      // unwrapResponse already surfaced a toast; keep local state as-is.
    }
  }, [bookmarks]);

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="gap-0">
    <FlushPage
      contentClassName="gap-0 pt-0"
      toolbarAside={
        activeTab === "calendar" ? (
          <TooltipIconButton
            label={t("marketOverview.refresh")}
            variant="outline"
            size={radarControlSizes.iconAction}
            style={controlStyle}
            onClick={loadCalendar}
            disabled={calendarLoading}
          >
            <RefreshCw className={calendarLoading ? "animate-spin" : ""} />
          </TooltipIconButton>
        ) : user ? (
          <TooltipIconButton
            label={t("radar.myBookmarks")}
            variant="outline"
            size={radarControlSizes.iconAction}
            style={controlStyle}
            onClick={() => navigate("/radar/bookmarks")}
          >
            <Bookmark />
          </TooltipIconButton>
        ) : null
      }
      toolbar={
        <div className="flex items-center gap-3">
          <TabsList variant="line" className="h-7 gap-3 p-0">
            <TabsTrigger
              value="feed"
              style={radarControlSizes.tabStyle}
              className={animatedLineTabClassName}
            >
              {t("radar.tab.feed")}
            </TabsTrigger>
            <TabsTrigger
              value="calendar"
              style={radarControlSizes.tabStyle}
              className={animatedLineTabClassName}
            >
              {t("radar.tab.calendar")}
            </TabsTrigger>
          </TabsList>
          {activeTab === "feed" ? <>
          <ToggleGroup
            type="single" value={category}
            onValueChange={(v) => v && setCategory(v as RadarCategory)}
            variant="default" size={radarControlSizes.filter}
            spacing={1}
            className="h-7 gap-0 rounded-none"
          >
            {RADAR_CATEGORIES.map((c) => (
              <ToggleGroupItem
                key={c}
                value={c}
                style={controlStyle}
                className="h-7 rounded-none border-b-2 border-transparent px-2.5 font-normal text-muted-foreground hover:bg-transparent hover:text-foreground data-[state=on]:border-[var(--market-info)] data-[state=on]:!bg-transparent data-[state=on]:text-foreground"
              >
                {t(`radar.category.${c}`)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <div className="relative w-[220px] shrink-0">
            <Search className="pointer-events-none absolute left-0 top-1/2 size-[var(--icon-xs)] -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("radar.searchPlaceholder")}
              className="h-7 rounded-none border-0 border-b border-[var(--data-grid-line)] bg-transparent pl-5 pr-1 shadow-none focus-visible:border-[var(--market-info)] focus-visible:ring-0"
              style={controlStyle}
            />
          </div>
          </> : null}
        </div>
      }
    >
      <TabsContent value="feed" className="relative mt-0">
      <div ref={scrollRef} className="absolute top-0" />
      {newCount > 0 && bannerBox ? (
        <button
          type="button"
          onClick={refreshTop}
          className={`fixed z-30 inline-flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-[var(--accent-strong)] bg-[var(--accent-soft)] px-3 py-1 font-medium text-[var(--accent)] shadow-md backdrop-blur transition-colors hover:bg-[var(--accent)] hover:text-white ${radarControlSizes.metaTextClassName}`}
          style={{ ...controlStyle, top: bannerBox.top, left: bannerBox.left }}
        >
          <ArrowUp size={14} strokeWidth={2} />
          {t("radar.newItems", { count: newCount })}
        </button>
      ) : null}
      <div className="-mx-4 flex min-h-10 overflow-x-auto border-b border-[var(--data-grid-line)] bg-[var(--data-panel-header-bg)] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <div className="flex min-w-[160px] items-center gap-2 border-r border-[var(--data-grid-line)] px-4">
          <span className={`size-1.5 rounded-full ${loading ? "animate-pulse bg-[var(--market-warning)]" : feedFailed ? "bg-[var(--market-down)]" : "bg-[var(--market-up)]"}`} />
          <span className="text-micro font-semibold uppercase tracking-[0.12em] text-foreground">{t("radar.streamStatus")}</span>
          <span className="market-data-value text-micro text-muted-foreground">
            {loading ? t("radar.loading") : feedFailed ? t("radar.streamUnavailable") : t("radar.streamOnline")}
          </span>
        </div>
        <div className="flex min-w-[120px] items-center justify-between gap-3 border-r border-[var(--data-grid-line)] px-4 text-micro">
          <span className="uppercase tracking-wide text-muted-foreground">{t("radar.total")}</span>
          <span className="market-data-value text-foreground">{total}</span>
        </div>
        <div className="flex min-w-[120px] items-center justify-between gap-3 border-r border-[var(--data-grid-line)] px-4 text-micro">
          <span className="uppercase tracking-wide text-muted-foreground">{t("radar.sources")}</span>
          <span className="market-data-value text-foreground">{sourceCount}</span>
        </div>
        <div className="flex min-w-[120px] items-center justify-between gap-3 border-r border-[var(--data-grid-line)] px-4 text-micro">
          <span className="uppercase tracking-wide text-muted-foreground">{t("radar.visible")}</span>
          <span className="market-data-value text-foreground">{items.length}</span>
        </div>
        <div className="ml-auto flex min-w-[190px] items-center justify-end gap-3 px-4 text-micro">
          <span className="uppercase tracking-wide text-muted-foreground">{t("radar.latest")}</span>
          <span className="market-data-value text-foreground">
            {latestItemTime ? new Date(latestItemTime).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
          </span>
        </div>
      </div>

      <div className="grid items-start gap-3 pt-3 xl:grid-cols-[minmax(0,1fr)_320px]">
        <section className="overflow-hidden rounded-[var(--radius-data-panel)] border border-[var(--data-grid-line)] bg-[var(--data-panel-bg)]">
          <header className="flex min-h-9 items-center justify-between border-b border-[var(--data-grid-line)] bg-[var(--data-panel-header-bg)] px-3">
            <h2 className="text-micro font-semibold uppercase tracking-[0.12em] text-muted-foreground">{t("radar.streamTitle")}</h2>
            <span className="market-data-value text-micro text-muted-foreground">{items.length} / {total}</span>
          </header>
          {items.length === 0 && !loading ? (
            <p className={`px-4 py-10 text-center text-muted-foreground ${radarControlSizes.metaTextClassName}`}>
              {t("radar.empty")}
            </p>
          ) : (
            <div className="flex flex-col">
              {items.map((item) => (
                <FeedItemCard
                  key={item.id}
                  item={item}
                  bookmarked={bookmarkedIds.has(item.id)}
                  canBookmark={!!user}
                  onToggleBookmark={handleToggleBookmark}
                  onOpen={(it) => navigate(`/radar/${it.id}`)}
                />
              ))}
              <div ref={sentinelRef} className="h-px" />
              {loading ? (
                <p className={`py-3 text-center text-muted-foreground ${radarControlSizes.metaTextClassName}`}>
                  {t("radar.loading")}
                </p>
              ) : items.length >= total && total > 0 ? (
                <p className={`py-3 text-center text-muted-foreground ${radarControlSizes.metaTextClassName}`}>
                  {t("radar.end")}
                </p>
              ) : null}
            </div>
          )}
        </section>
        <aside className="xl:sticky xl:top-[calc(var(--page-topbar-height)+12px)]">
          <BriefingCard briefing={briefing} category={category} />
        </aside>
      </div>
      </TabsContent>
      <TabsContent value="calendar" className="mt-0 pt-3">
        <EconomicCalendar
          items={calendar?.items ?? []}
          sourceUrl={calendar?.source_url}
          language={resolvedLanguage}
          selectedDate={selectedDate}
          onSelectedDateChange={setSelectedDate}
          unavailable={Boolean(calendar?.error)}
        />
      </TabsContent>
    </FlushPage>
    </Tabs>
  );
}
