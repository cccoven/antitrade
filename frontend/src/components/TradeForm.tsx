import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, Clock3, Star } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { DateTimePicker } from "@/components/ui/datetime-picker";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import TradeImageUploader from "@/components/TradeImageUploader";
import ComplianceSummaryCard from "@/components/ComplianceSummaryCard";
import { journalTradeFormControlSizes } from "@/pages/journal-ui-config";
import { inputStyle } from "@/pages/strategies-ui-config";
import { useToast } from "@/components/Toast";
import {
  createTrade,
  updateTrade,
  checkTradeCompliance,
  searchMarketInstruments,
  type Trade,
  type TradePlan,
  type ComplianceSummary,
  type CreateTradeRequest,
  type MarketInstrumentMatch,
  type UpdateTradeRequest,
  type UploadedAsset,
  type TradeImage,
} from "@/api/client";
import {
  type StrategyOption,
  listStrategyOptions,
} from "@/api/strategies";
import { useJournalSettings } from "@/journal/journal-settings-context";

interface TradeFormProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  trade?: Trade | null;
  initialPlan?: TradePlan | null;
}

const MISTAKE_OPTIONS = [
  "chased_entry", "moved_stop", "over_sized", "no_plan",
  "early_exit", "late_exit", "wrong_direction", "ignored_signal",
] as const;

const TRADE_DRAFT_STORAGE_KEY = "antitrade:journal:trade-draft:v1";

interface TradeDraft {
  symbol: string;
  exchange: string;
  seriesId: string | null;
  direction: "long" | "short";
  positionStatus: "open" | "closed";
  openPrice: string;
  closePrice: string;
  quantity: string;
  openTime: string;
  closeTime: string;
  fees: string;
  pnl: string;
  tags: string;
  notes: string;
  strategyId: string;
  planId: string;
  targetPrice: string;
  stopLoss: string;
  setupType: string;
  emotionalState: string;
  mistakes: string[];
  confidence: string;
  executionQuality: string;
}

function toDatetimeLocal(iso: string | null): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return "";
  }
}

function nowDatetimeLocal(): string {
  return toDatetimeLocal(new Date().toISOString());
}

function readTradeDraft(): TradeDraft | null {
  try {
    const raw = window.localStorage.getItem(TRADE_DRAFT_STORAGE_KEY);
    return raw ? JSON.parse(raw) as TradeDraft : null;
  } catch {
    return null;
  }
}

function hasTradeDraftContent(draft: TradeDraft): boolean {
  return draft.direction !== "long"
    || draft.positionStatus !== "open"
    || [
      draft.symbol,
      draft.openPrice,
      draft.closePrice,
      draft.quantity,
      draft.fees,
      draft.pnl,
      draft.tags,
      draft.notes,
      draft.strategyId,
      draft.planId,
      draft.targetPrice,
      draft.stopLoss,
      draft.setupType,
      draft.emotionalState,
      draft.confidence,
      draft.executionQuality,
    ].some((value) => value.trim().length > 0)
    || draft.mistakes.length > 0;
}

function writeTradeDraft(draft: TradeDraft): void {
  try {
    window.localStorage.setItem(TRADE_DRAFT_STORAGE_KEY, JSON.stringify(draft));
  } catch {
    // Draft persistence is a convenience; saving the trade must remain available.
  }
}

function clearTradeDraft(): void {
  try {
    window.localStorage.removeItem(TRADE_DRAFT_STORAGE_KEY);
  } catch {
    // Ignore unavailable browser storage.
  }
}

interface StarRatingProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

function StarRating({ label, value, onChange }: StarRatingProps) {
  const selected = Math.ceil((Number(value) || 0) / 2);
  const [preview, setPreview] = useState<number | null>(null);
  const visibleRating = preview ?? selected;

  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="flex items-center gap-0.5"
      onMouseLeave={() => setPreview(null)}
    >
      {[1, 2, 3, 4, 5].map((rating) => {
        const active = rating <= visibleRating;
        return (
          <Button
            key={rating}
            type="button"
            role="radio"
            aria-checked={rating === selected}
            aria-label={`${label} ${rating} / 5`}
            variant="ghost"
            size="icon-sm"
            className="rounded-full p-0 hover:bg-[var(--accent-ghost)]"
            style={{ fontSize: "var(--font-ui)" }}
            onMouseEnter={() => setPreview(rating)}
            onFocus={() => setPreview(rating)}
            onBlur={() => setPreview(null)}
            onClick={() => onChange(String(rating * 2))}
          >
            <Star
              className={
                active
                  ? "size-[var(--icon-md)] fill-[var(--market-warning)] text-[var(--market-warning)]"
                  : "size-[var(--icon-md)] text-muted-foreground/45"
              }
            />
          </Button>
        );
      })}
    </div>
  );
}

export default function TradeForm({
  open,
  onClose,
  onSaved,
  trade,
  initialPlan,
}: TradeFormProps) {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { currencyCode, formatMoney } = useJournalSettings();

  const isEdit = !!trade;

  const [symbol, setSymbol] = useState("");
  const [exchange, setExchange] = useState<string>(trade?.exchange ?? "");
  const [seriesId, setSeriesId] = useState<string | null>(trade?.series_id ?? null);
  const [marketOpen, setMarketOpen] = useState(false);
  const [marketQuery, setMarketQuery] = useState("");
  const [marketMatches, setMarketMatches] = useState<MarketInstrumentMatch[]>([]);
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [positionStatus, setPositionStatus] = useState<"open" | "closed">("open");
  const [openPrice, setOpenPrice] = useState("");
  const [closePrice, setClosePrice] = useState("");
  const [quantity, setQuantity] = useState("");
  const [openTime, setOpenTime] = useState("");
  const [closeTime, setCloseTime] = useState("");
  const [fees, setFees] = useState("");
  const [pnl, setPnl] = useState("");
  const [tags, setTags] = useState("");
  const [notes, setNotes] = useState("");
  const [images, setImages] = useState<(UploadedAsset | TradeImage)[]>([]);
  const [strategyId, setStrategyId] = useState<string>("");
  const [planId, setPlanId] = useState<string>("");
  const [targetPrice, setTargetPrice] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [setupType, setSetupType] = useState("");
  const [emotionalState, setEmotionalState] = useState("");
  const [mistakes, setMistakes] = useState<string[]>([]);
  const [confidence, setConfidence] = useState("");
  const [executionQuality, setExecutionQuality] = useState("");
  const [compliance, setCompliance] = useState<ComplianceSummary | null>(null);
  const [strategyOptions, setStrategyOptions] = useState<StrategyOption[]>([]);
  const [saving, setSaving] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [draftReady, setDraftReady] = useState(false);
  const [draftRestored, setDraftRestored] = useState(false);

  // Pre-fill on open with trade prop
  useEffect(() => {
    if (open && trade) {
      setDraftReady(false);
      setDraftRestored(false);
      setReviewOpen(true);
      setSymbol(trade.symbol);
      setExchange(trade.exchange ?? "");
      setSeriesId(trade.series_id);
      setDirection(trade.direction);
      setPositionStatus(trade.position_status);
      setOpenPrice(trade.open_price != null ? String(trade.open_price) : "");
      setClosePrice(trade.close_price != null ? String(trade.close_price) : "");
      setQuantity(trade.quantity != null ? String(trade.quantity) : "");
      setOpenTime(toDatetimeLocal(trade.open_time));
      setCloseTime(toDatetimeLocal(trade.close_time));
      setFees(trade.fees ? String(trade.fees) : "");
      setPnl(trade.pnl != null ? String(trade.pnl) : "");
      setTags(trade.tags.join(", "));
      setNotes(trade.notes);
      setImages(trade.images ?? []);
      setStrategyId(trade.strategy_id ?? "");
      setPlanId(trade.plan_id ?? "");
      setTargetPrice(trade.target_price != null ? String(trade.target_price) : "");
      setStopLoss(trade.stop_loss != null ? String(trade.stop_loss) : "");
      setSetupType(trade.setup_type ?? "");
      setEmotionalState(trade.emotional_state ?? "");
      setMistakes(trade.mistakes ?? []);
      setConfidence(trade.confidence != null ? String(trade.confidence) : "");
      setExecutionQuality(trade.execution_quality != null ? String(trade.execution_quality) : "");
      setCompliance(trade.compliance ?? null);
    } else if (open && !trade) {
      const storedDraft = initialPlan ? null : readTradeDraft();
      const draft = storedDraft && hasTradeDraftContent(storedDraft) ? storedDraft : null;
      setDraftRestored(!!draft);
      setReviewOpen(false);
      setSymbol(initialPlan?.symbol ?? draft?.symbol ?? "");
      setExchange(draft?.exchange ?? "");
      setSeriesId(initialPlan?.series_id ?? draft?.seriesId ?? null);
      setDirection(initialPlan?.direction ?? draft?.direction ?? "long");
      setPositionStatus(draft?.positionStatus ?? "open");
      setOpenPrice(initialPlan ? String(initialPlan.entry_price) : draft?.openPrice ?? "");
      setClosePrice(draft?.closePrice ?? "");
      setQuantity(initialPlan?.quantity != null ? String(initialPlan.quantity) : draft?.quantity ?? "");
      setOpenTime(draft?.openTime || nowDatetimeLocal());
      setCloseTime(draft?.closeTime ?? "");
      setFees(draft?.fees ?? "");
      setPnl(draft?.pnl ?? "");
      setTags(draft?.tags ?? "");
      setNotes(initialPlan?.thesis ?? draft?.notes ?? "");
      setImages([]);
      setStrategyId(initialPlan?.strategy_id ?? draft?.strategyId ?? "");
      setPlanId(initialPlan?.id ?? draft?.planId ?? "");
      setTargetPrice(initialPlan?.target_price != null ? String(initialPlan.target_price) : draft?.targetPrice ?? "");
      setStopLoss(initialPlan ? String(initialPlan.stop_loss) : draft?.stopLoss ?? "");
      setSetupType(draft?.setupType ?? "");
      setEmotionalState(draft?.emotionalState ?? "");
      setMistakes(draft?.mistakes ?? []);
      setConfidence(draft?.confidence ?? "");
      setExecutionQuality(draft?.executionQuality ?? "");
      setCompliance(null);
      setDraftReady(true);
    }
  }, [initialPlan, open, trade]);

  useEffect(() => {
    if (!open || trade || !draftReady) return;
    const draft: TradeDraft = {
      symbol,
      exchange,
      seriesId,
      direction,
      positionStatus,
      openPrice,
      closePrice,
      quantity,
      openTime,
      closeTime,
      fees,
      pnl,
      tags,
      notes,
      strategyId,
      planId,
      targetPrice,
      stopLoss,
      setupType,
      emotionalState,
      mistakes,
      confidence,
      executionQuality,
    };
    if (hasTradeDraftContent(draft)) {
      writeTradeDraft(draft);
    } else {
      clearTradeDraft();
    }
  }, [
    closePrice,
    closeTime,
    confidence,
    direction,
    draftReady,
    emotionalState,
    exchange,
    executionQuality,
    fees,
    mistakes,
    notes,
    open,
    openPrice,
    openTime,
    planId,
    pnl,
    positionStatus,
    quantity,
    seriesId,
    setupType,
    stopLoss,
    strategyId,
    symbol,
    tags,
    targetPrice,
    trade,
  ]);

  // Fetch strategy options when form opens
  useEffect(() => {
    if (!open) return;
    listStrategyOptions().then(setStrategyOptions).catch(() => setStrategyOptions([]));
  }, [open]);

  useEffect(() => {
    const query = marketQuery.trim();
    if (!marketOpen || !query) {
      setMarketMatches([]);
      return;
    }
    let active = true;
    const timer = window.setTimeout(() => {
      searchMarketInstruments(query)
        .then((matches) => {
          if (active) setMarketMatches(matches);
        })
        .catch(() => {
          if (active) setMarketMatches([]);
        });
    }, 200);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [marketOpen, marketQuery]);

  // Auto-calculate PnL hint
  const computedPnl = useCallback(() => {
    const op = parseFloat(openPrice);
    const cp = parseFloat(closePrice);
    const q = parseFloat(quantity);
    if (isNaN(op) || isNaN(cp) || isNaN(q)) return null;
    const raw = direction === "long" ? (cp - op) * q : (op - cp) * q;
    const f = parseFloat(fees) || 0;
    return raw - f;
  }, [openPrice, closePrice, quantity, direction, fees]);

  const handleSave = async () => {
    if (!symbol.trim()) return;
    setSaving(true);
    try {
      const parsedTags = tags
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const imageAssetIds = images.map((img) => ("asset_id" in img ? img.asset_id : img.id));
      const strategyValue: string | null = strategyId || null;
      const structuredFields = {
        position_status: positionStatus,
        plan_id: planId || null,
        target_price: targetPrice ? parseFloat(targetPrice) : null,
        stop_loss: stopLoss ? parseFloat(stopLoss) : null,
        setup_type: setupType.trim() || null,
        emotional_state: emotionalState || null,
        mistakes,
        confidence: confidence ? parseInt(confidence, 10) : null,
        execution_quality: executionQuality ? parseInt(executionQuality, 10) : null,
      };

      if (isEdit && trade) {
        const req: UpdateTradeRequest = {
          symbol: symbol.trim(),
          series_id: seriesId,
          exchange: exchange.trim() || null,
          direction,
          open_price: openPrice ? parseFloat(openPrice) : null,
          close_price: closePrice ? parseFloat(closePrice) : null,
          quantity: quantity ? parseFloat(quantity) : null,
          open_time: openTime ? new Date(openTime).toISOString() : null,
          close_time: closeTime ? new Date(closeTime).toISOString() : null,
          fees: fees ? parseFloat(fees) : null,
          pnl: pnl ? parseFloat(pnl) : null,
          tags: parsedTags,
          notes,
          strategy_id: strategyValue,
          image_asset_ids: imageAssetIds,
          ...structuredFields,
        };
        await updateTrade(trade.id, req);
        showToast(t("journal.tradeUpdated"), "success");
      } else {
        const req: CreateTradeRequest = {
          symbol: symbol.trim(),
          series_id: seriesId,
          exchange: exchange.trim() || null,
          direction,
          open_price: openPrice ? parseFloat(openPrice) : null,
          close_price: closePrice ? parseFloat(closePrice) : null,
          quantity: quantity ? parseFloat(quantity) : null,
          open_time: openTime ? new Date(openTime).toISOString() : null,
          close_time: closeTime ? new Date(closeTime).toISOString() : null,
          fees: fees ? parseFloat(fees) : 0,
          pnl: pnl ? parseFloat(pnl) : null,
          tags: parsedTags,
          notes,
          strategy_id: strategyValue,
          image_asset_ids: imageAssetIds,
          ...structuredFields,
        };
        await createTrade(req);
        clearTradeDraft();
        setDraftReady(false);
        showToast(t("journal.tradeCreated"), "success");
      }
      onSaved();
      onClose();
    } catch {
      // Error toast is handled by unwrapResponse in client.ts
    } finally {
      setSaving(false);
    }
  };

  const handleComplianceCheck = async () => {
    if (!symbol.trim()) return;
    const result = await checkTradeCompliance({
      symbol: symbol.trim(),
      direction,
      open_price: openPrice ? parseFloat(openPrice) : null,
      target_price: targetPrice ? parseFloat(targetPrice) : null,
      stop_loss: stopLoss ? parseFloat(stopLoss) : null,
      quantity: quantity ? parseFloat(quantity) : null,
      open_time: openTime ? new Date(openTime).toISOString() : null,
      notes,
      confidence: confidence ? parseInt(confidence, 10) : null,
      plan_id: planId || null,
    });
    setCompliance(result);
  };

  const hint = computedPnl();
  const compactInputClassName = `h-8 ${journalTradeFormControlSizes.inputPlaceholderClassName}`;

  const dateTimeProps = {
    buttonSize: journalTradeFormControlSizes.dateTimeButton,
    buttonStyle: {
      fontSize: journalTradeFormControlSizes.fieldValueFontSize,
      fontWeight: journalTradeFormControlSizes.fieldValueFontWeight,
    },
    placeholderStyle: {
      fontSize: journalTradeFormControlSizes.dateTimePlaceholderFontSize,
    },
    calendarClassNames: {
      dropdowns: "text-[length:var(--font-ui)] font-normal",
      caption_label: "text-[length:var(--font-ui)] font-normal",
      weekday: "text-[length:var(--font-caption)] font-normal text-muted-foreground",
      week_number: "text-[length:var(--font-caption)] text-muted-foreground",
    },
    timeInputClassName: journalTradeFormControlSizes.timeInputClassName,
    timeInputStyle: {
      fontSize: journalTradeFormControlSizes.dateTimeTimeInputFontSize,
      fontWeight: journalTradeFormControlSizes.dateTimeTimeInputFontWeight,
    },
  } as const;

  const buttonStyle = {
    fontSize: journalTradeFormControlSizes.fontSize,
    fontWeight: journalTradeFormControlSizes.fontWeight,
  };

  return (
    <Sheet open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <SheetContent
        side="right"
        showCloseButton={false}
        className="trade-form border-l-0 p-0 sm:max-w-xl"
      >
        <SheetHeader className="trade-form-head border-b border-border">
          <div className="min-w-0">
            <SheetTitle className="trade-form-title">
              {isEdit ? trade.symbol : t("journal.quickEntry.title")}
            </SheetTitle>
            <p className="mt-1 text-caption font-normal text-muted-foreground">
              {isEdit ? t("journal.quickEntry.editHint") : t("journal.quickEntry.hint")}
            </p>
          </div>
        </SheetHeader>

        <div className="trade-form-body gap-4">
          <section className="rounded-xl border border-border bg-card p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-ui font-semibold">{t("journal.quickEntry.section")}</p>
                <p className="mt-0.5 text-caption text-muted-foreground">
                  {t("journal.quickEntry.requiredHint")}
                </p>
              </div>
              {draftRestored && !isEdit ? (
                <span className="shrink-0 rounded-full bg-muted px-2 py-1 text-caption text-muted-foreground">
                  {t("journal.quickEntry.draftRestored")}
                </span>
              ) : null}
            </div>

            <FieldGroup className="gap-4">
              <Field>
                <FieldLabel className="text-caption font-medium text-muted-foreground">
                  {t("journal.quickEntry.instrument")}
                </FieldLabel>
                <Popover
                  open={marketOpen}
                  onOpenChange={(nextOpen) => {
                    setMarketOpen(nextOpen);
                    setMarketQuery(nextOpen ? symbol : "");
                  }}
                >
                  <PopoverTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-auto min-h-10 w-full justify-between px-3 py-2 font-normal"
                      style={buttonStyle}
                    >
                      <span className="min-w-0 text-left">
                        <span className={symbol ? "block truncate text-ui text-foreground" : "block truncate text-ui text-muted-foreground"}>
                          {symbol || t("journal.quickEntry.instrumentPlaceholder")}
                        </span>
                        {symbol ? (
                          <span className="mt-0.5 block truncate text-caption text-muted-foreground">
                            {seriesId
                              ? `${exchange || t("journal.marketSeries")} · ${t("journal.marketSeriesMatched")}`
                              : t("journal.quickEntry.unmatchedHint")}
                          </span>
                        ) : null}
                      </span>
                      <ChevronDown className="size-[var(--icon-xs)] shrink-0 opacity-50" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
                    <Command shouldFilter={false}>
                      <CommandInput
                        value={marketQuery}
                        onValueChange={(value) => {
                          setMarketQuery(value);
                          setSymbol(value.trim().toUpperCase());
                          setSeriesId(null);
                          setExchange("");
                        }}
                        placeholder={t("symbol.searchPlaceholder")}
                        style={{ fontSize: "var(--font-ui)" }}
                      />
                      <CommandList>
                        <CommandEmpty>{t("symbol.noMatches")}</CommandEmpty>
                        <CommandGroup>
                          {marketQuery.trim() ? (
                            <CommandItem
                              value={`manual:${marketQuery}`}
                              onSelect={() => {
                                setSymbol(marketQuery.trim().toUpperCase());
                                setSeriesId(null);
                                setMarketOpen(false);
                              }}
                            >
                              <span className="min-w-0 flex-1">
                                <span className="block truncate text-ui font-medium">
                                  {t("journal.quickEntry.useSymbol", { symbol: marketQuery.trim().toUpperCase() })}
                                </span>
                                <span className="block text-caption text-muted-foreground">
                                  {t("journal.quickEntry.saveWithoutReplay")}
                                </span>
                              </span>
                            </CommandItem>
                          ) : null}
                          {marketMatches.map((match) => (
                            <CommandItem
                              key={match.series_id}
                              value={match.series_id}
                              onSelect={() => {
                                setSeriesId(match.series_id);
                                setSymbol(match.symbol);
                                setExchange(match.venue ?? "");
                                setMarketOpen(false);
                                setMarketQuery("");
                              }}
                            >
                              <span className="min-w-0 flex-1">
                                <span className="block truncate text-ui font-medium">
                                  {match.symbol}
                                </span>
                                <span className="block truncate text-caption text-muted-foreground">
                                  {match.name}
                                </span>
                              </span>
                              <span className="text-caption text-muted-foreground">
                                {match.venue ?? match.series_kind}
                              </span>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </Field>

              <div className="grid grid-cols-2 gap-3">
                <Field>
                  <FieldLabel className="text-caption font-medium text-muted-foreground">
                    {t("journal.direction")}
                  </FieldLabel>
                  <ToggleGroup
                    type="single"
                    variant="outline"
                    size={journalTradeFormControlSizes.toggle}
                    value={direction}
                    onValueChange={(value) => value && setDirection(value as "long" | "short")}
                    className="w-full"
                  >
                    <ToggleGroupItem
                      value="long"
                      style={buttonStyle}
                      className="flex-1 data-[state=on]:bg-[color-mix(in_srgb,var(--success)_16%,transparent)] data-[state=on]:text-[var(--success)]"
                    >
                      {t("journal.long")}
                    </ToggleGroupItem>
                    <ToggleGroupItem
                      value="short"
                      style={buttonStyle}
                      className="flex-1 data-[state=on]:bg-[color-mix(in_srgb,var(--danger)_16%,transparent)] data-[state=on]:text-[var(--danger)]"
                    >
                      {t("journal.short")}
                    </ToggleGroupItem>
                  </ToggleGroup>
                </Field>

                <Field>
                  <FieldLabel className="text-caption font-medium text-muted-foreground">
                    {t("journal.positionStatus")}
                  </FieldLabel>
                  <ToggleGroup
                    type="single"
                    variant="outline"
                    size={journalTradeFormControlSizes.toggle}
                    value={positionStatus}
                    onValueChange={(value) => {
                      if (!value) return;
                      const next = value as "open" | "closed";
                      setPositionStatus(next);
                      if (next === "closed" && !closeTime) setCloseTime(nowDatetimeLocal());
                      if (next === "open") {
                        setClosePrice("");
                        setCloseTime("");
                        setPnl("");
                      }
                    }}
                    className="w-full"
                  >
                    <ToggleGroupItem value="open" style={buttonStyle} className="flex-1">
                      {t("journal.status.open")}
                    </ToggleGroupItem>
                    <ToggleGroupItem value="closed" style={buttonStyle} className="flex-1">
                      {t("journal.status.closed")}
                    </ToggleGroupItem>
                  </ToggleGroup>
                </Field>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Field>
                  <FieldLabel htmlFor="trade-open-price" className="text-caption font-medium text-muted-foreground">
                    {t("journal.openPrice")}
                  </FieldLabel>
                  <Input
                    id="trade-open-price"
                    className={compactInputClassName}
                    style={inputStyle}
                    type="number"
                    step="any"
                    inputMode="decimal"
                    value={openPrice}
                    onChange={(event) => setOpenPrice(event.target.value)}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="trade-quantity" className="text-caption font-medium text-muted-foreground">
                    {t("journal.quantity")}
                  </FieldLabel>
                  <Input
                    id="trade-quantity"
                    className={compactInputClassName}
                    style={inputStyle}
                    type="number"
                    step="any"
                    inputMode="decimal"
                    value={quantity}
                    onChange={(event) => setQuantity(event.target.value)}
                  />
                </Field>
              </div>

              <Field>
                <FieldLabel className="text-caption font-medium text-muted-foreground">
                  {t("journal.openTime")}
                </FieldLabel>
                <div className="flex gap-2">
                  <div className="min-w-0 flex-1">
                    <DateTimePicker
                      value={openTime}
                      onChange={setOpenTime}
                      placeholder={t("journal.openTime")}
                      {...dateTimeProps}
                    />
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon-sm"
                    style={buttonStyle}
                    aria-label={t("journal.quickEntry.useCurrentTime")}
                    title={t("journal.quickEntry.useCurrentTime")}
                    onClick={() => setOpenTime(nowDatetimeLocal())}
                  >
                    <Clock3 className="size-[var(--icon-sm)]" />
                  </Button>
                </div>
              </Field>

              {positionStatus === "closed" ? (
                <div className="rounded-lg border border-border bg-muted/30 p-3">
                  <p className="mb-3 text-caption font-medium text-muted-foreground">
                    {t("journal.quickEntry.exitSection")}
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    <Field>
                      <FieldLabel htmlFor="trade-close-price" className="text-caption font-medium text-muted-foreground">
                        {t("journal.closePrice")}
                      </FieldLabel>
                      <Input
                        id="trade-close-price"
                        className={compactInputClassName}
                        style={inputStyle}
                        type="number"
                        step="any"
                        inputMode="decimal"
                        value={closePrice}
                        onChange={(event) => setClosePrice(event.target.value)}
                      />
                    </Field>
                    <Field>
                      <FieldLabel className="text-caption font-medium text-muted-foreground">
                        {t("journal.closeTime")}
                      </FieldLabel>
                      <DateTimePicker
                        value={closeTime}
                        onChange={setCloseTime}
                        placeholder={t("journal.closeTime")}
                        {...dateTimeProps}
                      />
                    </Field>
                  </div>
                  {hint != null ? (
                    <div className="mt-3 flex items-center justify-between rounded-md bg-background px-3 py-2">
                      <span className="text-caption text-muted-foreground">
                        {t("journal.quickEntry.estimatedPnl")}
                      </span>
                      <span className={hint >= 0 ? "text-ui font-semibold text-[var(--success)]" : "text-ui font-semibold text-[var(--danger)]"}>
                        {formatMoney(hint, { signed: true })}
                      </span>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </FieldGroup>
          </section>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-auto w-full justify-between rounded-xl border border-border px-4 py-3 text-left"
            style={buttonStyle}
            onClick={() => setReviewOpen((current) => !current)}
          >
            <span>
              <span className="block text-ui font-semibold">{t("journal.review.title")}</span>
              <span className="mt-0.5 block text-caption font-normal text-muted-foreground">
                {t("journal.review.hint")}
              </span>
            </span>
            {reviewOpen ? (
              <ChevronDown className="size-[var(--icon-sm)] text-muted-foreground" />
            ) : (
              <ChevronRight className="size-[var(--icon-sm)] text-muted-foreground" />
            )}
          </Button>

          {reviewOpen ? (
            <div className="space-y-3">
              <section className="rounded-xl border border-border bg-card p-4">
                <h3 className="mb-4 text-ui font-semibold">{t("journal.review.plan")}</h3>
                <FieldGroup className="gap-4">
                  <div className="grid grid-cols-2 gap-3">
                    <Field>
                      <FieldLabel htmlFor="trade-stop-loss" className="text-caption text-muted-foreground">
                        {t("tradePlan.stop")}
                      </FieldLabel>
                      <Input
                        id="trade-stop-loss"
                        className={compactInputClassName}
                        style={inputStyle}
                        type="number"
                        step="any"
                        value={stopLoss}
                        onChange={(event) => setStopLoss(event.target.value)}
                      />
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="trade-target-price" className="text-caption text-muted-foreground">
                        {t("tradePlan.target")}
                      </FieldLabel>
                      <Input
                        id="trade-target-price"
                        className={compactInputClassName}
                        style={inputStyle}
                        type="number"
                        step="any"
                        value={targetPrice}
                        onChange={(event) => setTargetPrice(event.target.value)}
                      />
                    </Field>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <Field>
                      <FieldLabel htmlFor="trade-strategy" className="text-caption text-muted-foreground">
                        {t("strategies.linkLabel")}
                      </FieldLabel>
                      <Select
                        value={strategyId || "__none__"}
                        onValueChange={(value) => setStrategyId(value === "__none__" ? "" : value)}
                      >
                        <SelectTrigger id="trade-strategy" style={inputStyle}>
                          <SelectValue placeholder={t("strategies.linkPlaceholder")} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__none__">{t("strategies.linkPlaceholder")}</SelectItem>
                          {strategyOptions.map((strategy) => (
                            <SelectItem key={strategy.id} value={strategy.id}>
                              {strategy.title || "Untitled"}
                            </SelectItem>
                          ))}
                          {strategyOptions.length === 0 ? (
                            <div className="px-2 py-1.5 text-caption text-muted-foreground">
                              <Link to="/strategies" className="text-primary underline">
                                {t("strategies.linkEmptyHint")}
                              </Link>
                            </div>
                          ) : null}
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="trade-setup-type" className="text-caption text-muted-foreground">
                        {t("journal.setupType")}
                      </FieldLabel>
                      <Input
                        id="trade-setup-type"
                        className={compactInputClassName}
                        style={inputStyle}
                        value={setupType}
                        onChange={(event) => setSetupType(event.target.value)}
                        placeholder={t("journal.setupTypePlaceholder")}
                      />
                    </Field>
                  </div>
                </FieldGroup>
              </section>

              <section className="rounded-xl border border-border bg-card p-4">
                <h3 className="mb-4 text-ui font-semibold">{t("journal.review.execution")}</h3>
                <FieldGroup className="gap-4">
                  <Field>
                    <FieldLabel className="text-caption text-muted-foreground">
                      {t("journal.emotionalState")}
                    </FieldLabel>
                    <div className="flex flex-wrap gap-2">
                      {(["calm", "confident", "anxious", "fomo", "frustrated"] as const).map((value) => (
                        <Button
                          key={value}
                          type="button"
                          variant="outline"
                          size="sm"
                          aria-pressed={emotionalState === value}
                          style={buttonStyle}
                          className={
                            emotionalState === value
                              ? "h-8 rounded-full border-primary bg-primary px-3 text-primary-foreground shadow-none hover:bg-primary/90"
                              : "h-8 rounded-full border-border bg-transparent px-3 text-muted-foreground shadow-none hover:bg-muted hover:text-foreground"
                          }
                          onClick={() => setEmotionalState((current) => current === value ? "" : value)}
                        >
                          {t(`journal.emotion.${value}`)}
                        </Button>
                      ))}
                    </div>
                  </Field>

                  <Field>
                    <FieldLabel className="text-caption text-muted-foreground">
                      {t("journal.mistakes")}
                    </FieldLabel>
                    <div className="flex flex-wrap gap-2">
                      {MISTAKE_OPTIONS.map((value) => (
                        <Button
                          key={value}
                          type="button"
                          variant="outline"
                          size="sm"
                          aria-pressed={mistakes.includes(value)}
                          style={buttonStyle}
                          className={
                            mistakes.includes(value)
                              ? "h-8 rounded-full border-primary bg-primary px-3 text-primary-foreground shadow-none hover:bg-primary/90"
                              : "h-8 rounded-full border-border bg-transparent px-3 text-muted-foreground shadow-none hover:bg-muted hover:text-foreground"
                          }
                          onClick={() => setMistakes((current) => (
                            current.includes(value)
                              ? current.filter((item) => item !== value)
                              : [...current, value]
                          ))}
                        >
                          {t(`journal.mistake.${value}`)}
                        </Button>
                      ))}
                    </div>
                  </Field>

                  <div className="grid grid-cols-2 gap-3">
                    {([
                      ["confidence", confidence, setConfidence],
                      ["executionQuality", executionQuality, setExecutionQuality],
                    ] as const).map(([label, value, setter]) => (
                      <Field key={label}>
                        <FieldLabel className="text-caption text-muted-foreground">
                          {t(`journal.${label}`)}
                        </FieldLabel>
                        <StarRating
                          label={t(`journal.${label}`)}
                          value={value}
                          onChange={setter}
                        />
                      </Field>
                    ))}
                  </div>
                </FieldGroup>
              </section>

              <section className="rounded-xl border border-border bg-card p-4">
                <h3 className="mb-4 text-ui font-semibold">{t("journal.review.evidence")}</h3>
                <FieldGroup className="gap-4">
                  <Field>
                    <TradeImageUploader images={images} onChange={setImages} />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="trade-notes" className="text-caption text-muted-foreground">
                      {t("journal.notes")}
                    </FieldLabel>
                    <Textarea
                      id="trade-notes"
                      rows={journalTradeFormControlSizes.notesRows}
                      className="min-h-24 text-ui"
                      style={inputStyle}
                      value={notes}
                      onChange={(event) => setNotes(event.target.value)}
                      placeholder={t("journal.review.notesPlaceholder")}
                    />
                  </Field>
                </FieldGroup>
              </section>

              <section className="rounded-xl border border-border bg-card p-4">
                <h3 className="mb-4 text-ui font-semibold">{t("journal.review.details")}</h3>
                <FieldGroup className="gap-4">
                  <div className="grid grid-cols-2 gap-3">
                    <Field>
                      <FieldLabel htmlFor="trade-fees" className="text-caption text-muted-foreground">
                        {t("journal.fees")}{currencyCode ? ` (${currencyCode})` : ""}
                      </FieldLabel>
                      <Input
                        id="trade-fees"
                        className={compactInputClassName}
                        style={inputStyle}
                        type="number"
                        step="any"
                        value={fees}
                        onChange={(event) => setFees(event.target.value)}
                      />
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="trade-pnl" className="text-caption text-muted-foreground">
                        {t("journal.pnl")}{currencyCode ? ` (${currencyCode})` : ""}
                      </FieldLabel>
                      <Input
                        id="trade-pnl"
                        className={compactInputClassName}
                        style={inputStyle}
                        type="number"
                        step="any"
                        value={pnl}
                        onChange={(event) => setPnl(event.target.value)}
                        placeholder={hint != null ? hint.toFixed(2) : ""}
                      />
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Field>
                      <FieldLabel htmlFor="trade-tags" className="text-caption text-muted-foreground">
                        {t("journal.tags")}
                      </FieldLabel>
                      <Input
                        id="trade-tags"
                        className={compactInputClassName}
                        style={inputStyle}
                        value={tags}
                        onChange={(event) => setTags(event.target.value)}
                        placeholder="trend, breakout"
                      />
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="trade-exchange" className="text-caption text-muted-foreground">
                        {t("journal.exchange")}
                      </FieldLabel>
                      <Input
                        id="trade-exchange"
                        className={compactInputClassName}
                        style={inputStyle}
                        value={exchange}
                        onChange={(event) => {
                          setExchange(event.target.value);
                          setSeriesId(null);
                        }}
                        placeholder={t("journal.exchangePlaceholder")}
                      />
                    </Field>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    style={buttonStyle}
                    onClick={() => void handleComplianceCheck()}
                    disabled={saving || !symbol.trim()}
                  >
                    {t("compliance.check")}
                  </Button>
                  {compliance ? <ComplianceSummaryCard summary={compliance} /> : null}
                </FieldGroup>
              </section>
            </div>
          ) : null}
        </div>

        <SheetFooter className="trade-form-footer border-t border-border">
          <div className="flex w-full gap-2">
            <Button
              variant="outline"
              size="sm"
              className="flex-1"
              style={buttonStyle}
              onClick={onClose}
              disabled={saving}
            >
              {isEdit ? t("journal.cancel") : t("journal.quickEntry.finishLater")}
            </Button>
            <Button
              size="sm"
              className="flex-[1.4]"
              style={buttonStyle}
              onClick={handleSave}
              disabled={saving || !symbol.trim()}
            >
              {saving ? <span className="spinner" /> : t("journal.quickEntry.saveTrade")}
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
