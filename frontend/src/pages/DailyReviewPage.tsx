import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { Save, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { DateTimePicker } from "@/components/ui/datetime-picker";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import FlushPage from "@/components/FlushPage";
import ImagePreviewDialog from "@/components/ImagePreviewDialog";
import MarkdownDocument from "@/components/markdown/MarkdownDocument";
import LoginRequiredPage from "@/auth/LoginRequiredPage";
import { useAuth } from "@/auth/auth-context";
import { useToast } from "@/components/Toast";
import {
  assistDailyReview,
  getDailyReviewBundle,
  saveDailyReview,
  type DailyReviewAssistAction,
  type DailyReviewBundle,
  type TradeImage,
} from "@/api/client";
import { dailyReviewControlSizes, dailyReviewControlStyle } from "@/pages/daily-review-ui-config";
import { formatLocalDate, localDayRangeIso } from "@/pages/daily-review-utils";
import {
  parseReviewBody,
  serializeReviewBlocks,
  type ReviewBlock,
} from "@/pages/daily-review/parser";
import {
  insertEmbedAt,
  insertTextAt,
  removeEmbedAt,
} from "@/pages/daily-review/blocks";
import BlockEditor, {
  type BlockEditorHandle,
} from "@/pages/daily-review/BlockEditor";
import MaterialDrawer from "@/pages/daily-review/MaterialDrawer";
import AIDraft, { type AIDraftState } from "@/pages/daily-review/AIDraft";
import ReviewBody from "@/pages/daily-review/ReviewBody";
import DailyReviewShareView from "@/pages/DailyReviewShareView";

type Mode = "edit" | "read" | "share";

export default function DailyReviewPage() {
  const { t, i18n } = useTranslation();
  const { showToast } = useToast();
  const { user, loading: authLoading } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [date, setDate] = useState(
    searchParams.get("date") || formatLocalDate(new Date()),
  );
  const [mode, setMode] = useState<Mode>("edit");
  const [bundle, setBundle] = useState<DailyReviewBundle | null>(null);
  const [title, setTitle] = useState("");
  const [blocks, setBlocks] = useState<ReviewBlock[]>([{ kind: "text", text: "" }]);
  const [tags, setTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [previewImage, setPreviewImage] = useState<TradeImage | null>(null);
  const [aiState, setAIState] = useState<AIDraftState | null>(null);
  const editorRef = useRef<BlockEditorHandle>(null);
  const range = useMemo(() => localDayRangeIso(date), [date]);

  // Initial load
  useEffect(() => {
    if (!user) return;
    setSearchParams({ date }, { replace: true });
    let cancelled = false;
    setLoading(true);
    getDailyReviewBundle(date, range)
      .then((data) => {
        if (cancelled) return;
        setBundle(data);
        setTitle(data.review.title);
        setTags(data.review.tags);
        const stored = readDraft(date);
        if (stored && data.review.updated_at && stored.savedAt > Date.parse(data.review.updated_at)) {
          setTitle(stored.title);
          setBlocks(parseReviewBody(stored.body));
          setDirty(true);
          showToast(t("dailyReview.draft.restored"), "success");
        } else {
          setBlocks(parseReviewBody(data.review.body));
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [date, range, setSearchParams, user, t, showToast]);

  // Keep refs in sync so the interval can read latest values without being in its deps
  const titleRef = useRef(title);
  const blocksRef = useRef(blocks);
  useEffect(() => { titleRef.current = title; }, [title]);
  useEffect(() => { blocksRef.current = blocks; }, [blocks]);

  // Autosave to localStorage every 30s while dirty
  useEffect(() => {
    if (!dirty) return;
    const id = setInterval(() => {
      writeDraft(date, {
        title: titleRef.current,
        body: serializeReviewBlocks(blocksRef.current),
        savedAt: Date.now(),
      });
    }, 30000);
    return () => clearInterval(id);
  }, [dirty, date]);

  const handleBlocksChange = useCallback((next: ReviewBlock[]) => {
    setBlocks(next);
    setDirty(true);
  }, []);

  const handleTitleChange = useCallback((next: string) => {
    setTitle(next);
    setDirty(true);
  }, []);

  const insertEmbed = useCallback(
    (kind: "trade" | "screenshot", id: string) => {
      const anchor = editorRef.current?.getActiveAnchor() ?? {
        textBlockIndex: blocks.findIndex((b) => b.kind === "text"),
        cursor: 0,
      };
      if (anchor.textBlockIndex < 0) return;
      const next = insertEmbedAt(blocks, anchor, { kind, id } as Extract<
        ReviewBlock,
        { kind: "trade" | "screenshot" }
      >);
      handleBlocksChange(next);
    },
    [blocks, handleBlocksChange],
  );

  const insertStatsText = useCallback(
    (text: string) => {
      const anchor = editorRef.current?.getActiveAnchor();
      if (!anchor) {
        const lastTextIndex =
          blocks.length - 1 - [...blocks].reverse().findIndex((b) => b.kind === "text");
        if (lastTextIndex < 0) return;
        const last = blocks[lastTextIndex] as Extract<ReviewBlock, { kind: "text" }>;
        const next = insertTextAt(
          blocks,
          { textBlockIndex: lastTextIndex, cursor: last.text.length },
          (last.text ? "\n" : "") + text,
        );
        handleBlocksChange(next);
        return;
      }
      handleBlocksChange(insertTextAt(blocks, anchor, text));
    },
    [blocks, handleBlocksChange],
  );

  const removeEmbed = useCallback(
    (index: number) => {
      handleBlocksChange(removeEmbedAt(blocks, index));
    },
    [blocks, handleBlocksChange],
  );

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const review = await saveDailyReview(date, {
        title,
        body: serializeReviewBlocks(blocks),
        tags,
      });
      setBundle((prev) => (prev ? { ...prev, review } : prev));
      clearDraft(date);
      setDirty(false);
      showToast(t("dailyReview.saved"), "success");
    } catch {
      showToast(t("dailyReview.saveFailed"), "error");
    } finally {
      setSaving(false);
    }
  }, [blocks, date, showToast, t, tags, title]);

  // Save on Cmd/Ctrl+S
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (mode === "edit" && dirty) handleSave();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [dirty, handleSave, mode]);

  const switchDate = useCallback(
    async (next: string) => {
      if (next === date) return;
      if (dirty) {
        await handleSave();
      }
      setDate(next);
    },
    [date, dirty, handleSave],
  );

  const switchMode = useCallback(
    async (next: Mode) => {
      if (mode === "edit" && next !== "edit" && dirty) {
        await handleSave();
      }
      setMode(next);
    },
    [dirty, handleSave, mode],
  );

  const runAssist = useCallback(
    async (action: DailyReviewAssistAction) => {
      const anchor = editorRef.current?.getActiveAnchor();
      const selection =
        action === "organize" || action === "expand"
          ? anchor && blocks[anchor.textBlockIndex]?.kind === "text"
            ? (blocks[anchor.textBlockIndex] as Extract<ReviewBlock, { kind: "text" }>).text
            : ""
          : undefined;
      if ((action === "organize" || action === "expand") && !selection) {
        showToast(t("dailyReview.ai.requiresSelection"), "error");
        return;
      }
      setAIState({ kind: "loading", action });
      try {
        const res = await assistDailyReview(date, {
          action,
          body: serializeReviewBlocks(blocks),
          selection,
          ...range,
          lang: i18n.language.startsWith("zh") ? "zh" : "en",
        });
        if (res.suggestions.length === 0) {
          setAIState({ kind: "error", action });
          return;
        }
        setAIState({ kind: "ready", action, suggestions: res.suggestions });
      } catch {
        setAIState({ kind: "error", action });
      }
    },
    [blocks, date, i18n.language, range, showToast, t],
  );

  const adoptSuggestion = useCallback(
    (suggestion: string) => {
      if (!aiState) return;
      const action = aiState.action;

      const appendAtEnd = (text: string) => {
        const lastTextIndex =
          blocks.length - 1 - [...blocks].reverse().findIndex((b) => b.kind === "text");
        if (lastTextIndex < 0) return;
        const last = blocks[lastTextIndex] as Extract<ReviewBlock, { kind: "text" }>;
        const next = blocks.map((b, i) =>
          i === lastTextIndex && b.kind === "text"
            ? { ...b, text: (last.text ? last.text + "\n\n" : "") + text }
            : b,
        );
        handleBlocksChange(next);
      };

      if (action === "title") {
        handleTitleChange(suggestion);
      } else if (action === "organize") {
        const anchor = editorRef.current?.getActiveAnchor();
        if (anchor && blocks[anchor.textBlockIndex]?.kind === "text") {
          const next = blocks.map((b, i) =>
            i === anchor.textBlockIndex && b.kind === "text"
              ? { ...b, text: suggestion }
              : b,
          );
          handleBlocksChange(next);
        }
      } else if (action === "expand") {
        const anchor = editorRef.current?.getActiveAnchor();
        if (anchor && blocks[anchor.textBlockIndex]?.kind === "text") {
          const target = blocks[anchor.textBlockIndex] as Extract<ReviewBlock, { kind: "text" }>;
          const next = blocks.map((b, i) =>
            i === anchor.textBlockIndex && b.kind === "text"
              ? { ...b, text: (target.text ? target.text + "\n\n" : "") + suggestion }
              : b,
          );
          handleBlocksChange(next);
        } else {
          appendAtEnd(suggestion);
        }
      } else {
        // summary, suggest: append at end of body
        appendAtEnd(suggestion);
      }
      setAIState(null);
    },
    [aiState, blocks, handleBlocksChange, handleTitleChange],
  );

  if (authLoading) return null;
  if (!user) return <LoginRequiredPage />;

  return (
    <>
    <FlushPage
      toolbarAside={
        mode === "edit" ? (
            <div className="flex items-center gap-2">
              <Popover>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        size="icon-sm"
                        style={dailyReviewControlStyle}
                        aria-label={t("dailyReview.ai.menu")}
                      >
                        <Sparkles />
                      </Button>
                    </PopoverTrigger>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">{t("dailyReview.ai.menu")}</TooltipContent>
                </Tooltip>
                <PopoverContent className="flex w-[200px] flex-col gap-1">
                  {(["title", "summary", "organize", "expand", "suggest"] as DailyReviewAssistAction[]).map(
                    (action) => (
                      <Button
                        key={action}
                        variant="ghost"
                        size="sm"
                        style={dailyReviewControlStyle}
                        className="justify-start"
                        onClick={() => runAssist(action)}
                      >
                        {t(`dailyReview.ai.${action}`)}
                      </Button>
                    ),
                  )}
                </PopoverContent>
              </Popover>
              <TooltipIconButton
                label={saving ? t("dailyReview.saving") : t("dailyReview.save")}
                size="icon-sm"
                style={dailyReviewControlStyle}
                onClick={handleSave}
                disabled={saving || !dirty}
              >
                <Save />
              </TooltipIconButton>
            </div>
          ) : null
      }
      toolbar={
        <>
          <DateTimePicker
            value={`${date}T00:00`}
            onChange={(v) => switchDate(v.slice(0, 10))}
            placeholder={t("dailyReview.date")}
            buttonSize={dailyReviewControlSizes.input}
            buttonStyle={dailyReviewControlStyle}
            className="w-[140px]"
            showTime={false}
          />
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={mode}
            onValueChange={(v) => v && switchMode(v as Mode)}
          >
            <ToggleGroupItem value="edit" style={dailyReviewControlStyle}>
              {t("dailyReview.mode.edit")}
            </ToggleGroupItem>
            <ToggleGroupItem value="read" style={dailyReviewControlStyle}>
              {t("dailyReview.mode.read")}
            </ToggleGroupItem>
            <ToggleGroupItem value="share" style={dailyReviewControlStyle}>
              {t("dailyReview.mode.share")}
            </ToggleGroupItem>
          </ToggleGroup>
        </>
      }
    >
        {loading ? (
          <Skeleton className="h-[480px] w-full" />
        ) : mode === "edit" ? (
          <div className="mx-auto flex w-full max-w-[1240px] gap-4">
            <div className="flex min-w-0 flex-1 flex-col gap-3">
              <div className="rounded-xl border border-border bg-card/40 p-4 shadow-sm">
                <Input
                  value={title}
                  onChange={(e) => handleTitleChange(e.target.value)}
                  placeholder={t("dailyReview.titlePlaceholder")}
                  style={dailyReviewControlStyle}
                  className="border-transparent bg-transparent px-1 font-medium shadow-none focus-visible:border-transparent focus-visible:ring-0"
                />
              </div>
              <BlockEditor
                ref={editorRef}
                blocks={blocks}
                onChange={handleBlocksChange}
                trades={bundle?.trades ?? []}
                onPreviewImage={setPreviewImage}
                onRemoveEmbed={removeEmbed}
              />
              {aiState && (
                <AIDraft
                  state={aiState}
                  onAdopt={adoptSuggestion}
                  onRewrite={() => runAssist(aiState.action)}
                  onClose={() => setAIState(null)}
                />
              )}
            </div>
            <MaterialDrawer
              trades={bundle?.trades ?? []}
              stats={bundle?.stats ?? null}
              onInsertTrade={(id) => insertEmbed("trade", id)}
              onInsertScreenshot={(id) => insertEmbed("screenshot", id)}
              onInsertStats={(text) => insertStatsText(text)}
              onPreviewImage={setPreviewImage}
            />
          </div>
        ) : mode === "read" ? (
          <MarkdownDocument
            title={title}
            fallbackTitle={t("dailyReview.titleNav")}
            tags={tags}
            eyebrow={date}
          >
            <ReviewBody
              blocks={blocks}
              mode="read"
              trades={bundle?.trades ?? []}
              onPreviewImage={setPreviewImage}
            />
          </MarkdownDocument>
        ) : (
          <DailyReviewShareView
            date={date}
            title={title}
            blocks={blocks}
            bundle={bundle}
          />
        )}
    </FlushPage>

      <ImagePreviewDialog
        image={previewImage}
        open={previewImage != null}
        onOpenChange={(o) => !o && setPreviewImage(null)}
      />
    </>
  );
}

type LocalDraft = { title: string; body: string; savedAt: number };

function draftKey(date: string): string {
  return `dailyReview:draft:${date}`;
}

function readDraft(date: string): LocalDraft | null {
  try {
    const raw = localStorage.getItem(draftKey(date));
    if (!raw) return null;
    return JSON.parse(raw) as LocalDraft;
  } catch {
    return null;
  }
}

function writeDraft(date: string, draft: LocalDraft) {
  localStorage.setItem(draftKey(date), JSON.stringify(draft));
}

function clearDraft(date: string) {
  localStorage.removeItem(draftKey(date));
}
