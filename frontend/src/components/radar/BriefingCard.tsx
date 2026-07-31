import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Radio } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { radarControlSizes } from "@/pages/radar-ui-config";
import type { FeedBriefing } from "@/api/client";

interface Entry {
  title: string;
  id?: string;
}

export default function BriefingCard({
  briefing,
  category = "all",
  returnTo = "/radar",
}: {
  briefing: FeedBriefing | null;
  category?: string;
  returnTo?: string;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  if (!briefing) {
    return (
      <Card className="gap-0 overflow-hidden rounded-[var(--radius-data-panel)] border-[var(--data-grid-line)] bg-[var(--data-panel-bg)] py-0 shadow-none">
        <CardContent className="p-4">
          <p className={cn("text-muted-foreground", radarControlSizes.metaTextClassName)}>
            {t("radar.briefingEmpty")}
          </p>
        </CardContent>
      </Card>
    );
  }
  // "all" → the cross-category highlights. A specific category → that section's
  // points, rendered as the same numbered list (no per-category sub-headers).
  const entries: Entry[] = category === "all"
    ? briefing.content.hot.map((h) => ({ title: h.title, id: h.id }))
    : briefing.content.sections
        .filter((s) => s.category === category)
        .flatMap((s) => s.points)
        // Tolerate legacy briefings whose points were plain strings.
        .map((p) => (typeof p === "string" ? { title: p } : { title: p.text, id: p.id }));

  return (
    <Card className="gap-0 overflow-hidden rounded-[var(--radius-data-panel)] border-[var(--data-grid-line)] bg-[var(--data-panel-bg)] py-0 shadow-none">
      <header className="grid min-h-9 grid-cols-[1fr_auto] items-center gap-3 border-b border-[var(--data-grid-line)] bg-[var(--data-panel-header-bg)] px-3">
        <span className="flex min-w-0 items-center gap-2 leading-none">
          <Radio className="size-[var(--icon-xs)] shrink-0 text-[var(--market-info)]" strokeWidth={1.8} />
          <span className="text-micro font-semibold uppercase leading-none tracking-[0.12em] text-muted-foreground">{t("radar.hotTitle")}</span>
        </span>
        <span className="market-data-value text-micro leading-none text-muted-foreground">
          {t("radar.generatedAt", {
            time: new Date(briefing.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          })}
        </span>
      </header>
      <CardContent className="p-0">
        {entries.length === 0 ? (
          <p className={cn("p-4 text-muted-foreground", radarControlSizes.metaTextClassName)}>
            {t("radar.briefingEmpty")}
          </p>
        ) : (
          <ol className="flex flex-col">
            {entries.map((e, i) => (
              <li
                key={i}
                className={cn(
                  "flex gap-2 border-b border-[var(--data-grid-line)] px-3 py-2.5 text-foreground transition-colors last:border-b-0",
                  radarControlSizes.bodyTextClassName,
                  e.id && "group cursor-pointer hover:bg-muted/35",
                )}
                {...(e.id
                  ? {
                      role: "button",
                      tabIndex: 0,
                      onClick: () => navigate(`/radar/${e.id}`, { state: { from: returnTo } }),
                      onKeyDown: (ev: React.KeyboardEvent) => {
                        if (ev.key === "Enter" || ev.key === " ") {
                          ev.preventDefault();
                          navigate(`/radar/${e.id}`, { state: { from: returnTo } });
                        }
                      },
                    }
                  : {})}
              >
                <span className="market-data-value mt-0.5 text-micro font-semibold text-[var(--market-info)]">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className={cn(e.id && "transition-colors group-hover:text-[var(--accent)]")}>
                  {e.title}
                </span>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
