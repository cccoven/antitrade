import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronLeft, Trash2 } from "lucide-react";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import FlushPage from "@/components/FlushPage";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useAuth } from "@/auth/auth-context";
import LoginRequiredPage from "@/auth/LoginRequiredPage";
import {
  type Strategy,
  getStrategy, listStrategies, patchStrategy, deleteStrategy,
} from "@/api/strategies";
import StrategyEditor from "./strategies/StrategyEditor";
import StrategyView from "./strategies/StrategyView";
import { btnStyle } from "./strategies-ui-config";

type Mode = "read" | "edit";

export default function StrategyDetailPage() {
  const { id = "" } = useParams();
  const [search] = useSearchParams();
  const isNew = search.get("new") === "1";
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user, loading: authLoading } = useAuth();

  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>(isNew ? "edit" : "read");
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved">("idle");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [tagSuggestions, setTagSuggestions] = useState<string[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const debounceRef = useRef<number | null>(null);
  const pendingRef = useRef<{ title?: string; body?: string; tags?: string[] }>({});

  useEffect(() => {
    if (!user) return;
    getStrategy(id)
      .then((s) => {
        setStrategy(s);
        if (isNew || (!s.title && !s.body)) setMode("edit");
        else setMode("read");
      })
      .catch(() => setError("not_found"));
  }, [id, isNew, user]);

  useEffect(() => {
    if (!user) return;
    listStrategies()
      .then((all) => {
        const set = new Set<string>();
        all.forEach((s) => s.tags.forEach((t) => set.add(t)));
        setTagSuggestions(Array.from(set));
      })
      .catch(() => setTagSuggestions([]));
  }, [user]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, []);

  function update<K extends keyof Strategy>(key: K, value: Strategy[K]) {
    setStrategy((s) => (s ? { ...s, [key]: value } : s));
    if (key === "title" || key === "body" || key === "tags") {
      (pendingRef.current as Record<string, unknown>)[key] = value;
    }
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    setSaveStatus("saving");
    debounceRef.current = window.setTimeout(async () => {
      const diff = pendingRef.current;
      pendingRef.current = {};
      try {
        const updated = await patchStrategy(id, diff);
        setSavedAt(updated.updated_at);
        setSaveStatus("saved");
      } catch {
        setSaveStatus("idle");
      }
    }, 800);
  }

  async function onDelete() {
    await deleteStrategy(id);
    navigate("/strategies");
  }

  if (authLoading) return null;
  if (!user) return <LoginRequiredPage />;

  if (error === "not_found") {
    return (
      <div className="flex flex-col items-center gap-3 p-12">
        <div className="text-ui text-foreground">{t("strategies.notFound")}</div>
        <Link to="/strategies" className="text-ui text-primary underline">
          {t("strategies.backToGallery")}
        </Link>
      </div>
    );
  }

  if (!strategy) {
    return <div className="p-6 text-caption text-muted-foreground">{t("common.loading")}</div>;
  }

  return (
    <FlushPage
      contentClassName="gap-4 p-4 md:p-6"
      toolbar={
        <TooltipIconButton
          label={t("strategies.back")}
          variant="ghost"
          size="icon-sm"
          style={btnStyle}
          asChild
        >
          <Link to="/strategies">
            <ChevronLeft className="size-[var(--icon-md)]" />
          </Link>
        </TooltipIconButton>
      }
      toolbarAside={
        <div className="flex items-center gap-3">
          <ToggleGroup
            type="single"
            value={mode}
            onValueChange={(v) => v && setMode(v as Mode)}
            size="sm"
          >
            <ToggleGroupItem value="read" style={btnStyle}>{t("strategies.modeRead")}</ToggleGroupItem>
            <ToggleGroupItem value="edit" style={btnStyle}>{t("strategies.modeEdit")}</ToggleGroupItem>
          </ToggleGroup>

          <TooltipIconButton
            label={t("strategies.delete")}
            variant="ghost"
            size="icon-sm"
            onClick={() => setConfirmOpen(true)}
          >
            <Trash2 className="size-[var(--icon-sm)] text-destructive" />
          </TooltipIconButton>

          <ConfirmDialog
            open={confirmOpen}
            onOpenChange={setConfirmOpen}
            title={t("strategies.deleteConfirmTitle")}
            description={t("strategies.deleteConfirmBody")}
            onConfirm={onDelete}
            confirmLabel={t("strategies.delete")}
            cancelLabel={t("common.cancel")}
          />

          <div className="text-caption text-muted-foreground">
            {saveStatus === "saving" && t("strategies.saving")}
            {saveStatus === "saved" && savedAt && `${t("strategies.saved")} · ${formatTime(savedAt)}`}
          </div>
        </div>
      }
    >

      {mode === "edit" ? (
        <StrategyEditor
          title={strategy.title}
          body={strategy.body}
          tags={strategy.tags}
          tagSuggestions={tagSuggestions}
          onTitleChange={(v) => update("title", v)}
          onBodyChange={(v) => update("body", v)}
          onTagsChange={(v) => update("tags", v)}
          autoFocusTitle={isNew}
        />
      ) : (
        <StrategyView title={strategy.title} tags={strategy.tags} body={strategy.body} />
      )}
    </FlushPage>
  );
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
