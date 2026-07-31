import { useTranslation } from "react-i18next";
import { Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { dailyReviewControlStyle } from "@/pages/daily-review-ui-config";
import type { DailyReviewAssistAction } from "@/api/client";

export type AIDraftState =
  | { kind: "loading"; action: DailyReviewAssistAction }
  | { kind: "ready"; action: DailyReviewAssistAction; suggestions: string[] }
  | { kind: "error"; action: DailyReviewAssistAction };

export interface AIDraftProps {
  state: AIDraftState;
  onAdopt: (suggestion: string) => void;
  onRewrite: () => void;
  onClose: () => void;
}

export default function AIDraft({ state, onAdopt, onRewrite, onClose }: AIDraftProps) {
  const { t } = useTranslation();
  const actionLabel = t(`dailyReview.ai.${state.action}`);

  return (
    <div className="rounded-md border border-l-4 border-[var(--success)] bg-[var(--success)]/10 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-caption text-[var(--success)]">
          <Sparkles className="size-[var(--icon-xs)]" />
          <span>{t("dailyReview.ai.draft")} · {actionLabel}</span>
        </div>
        <Button variant="ghost" size="icon-xs" onClick={onClose}>
          <X />
        </Button>
      </div>

      {state.kind === "loading" && (
        <div className="mt-2 flex flex-col gap-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      )}

      {state.kind === "error" && (
        <div className="mt-2 flex items-center justify-between text-ui text-foreground">
          <span>{t("dailyReview.ai.error")}</span>
          <Button variant="outline" size="sm" style={dailyReviewControlStyle} onClick={onRewrite}>
            {t("dailyReview.ai.retry")}
          </Button>
        </div>
      )}

      {state.kind === "ready" && (
        <div className="mt-2 flex flex-col gap-2">
          {state.suggestions.length === 0 && (
            <div className="text-caption text-muted-foreground">
              {t("dailyReview.ai.empty")}
            </div>
          )}
          {state.suggestions.map((s, i) => (
            <div
              key={i}
              className="rounded border border-border bg-background/40 p-2 text-ui"
            >
              <div className="whitespace-pre-wrap">{s}</div>
              <div className="mt-1 flex gap-2">
                <Button size="sm" style={dailyReviewControlStyle} onClick={() => onAdopt(s)}>
                  {t("dailyReview.ai.adopt")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  style={dailyReviewControlStyle}
                  onClick={onRewrite}
                >
                  {t("dailyReview.ai.rewrite")}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
