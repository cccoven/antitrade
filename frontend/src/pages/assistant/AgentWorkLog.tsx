import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  LoaderCircle,
  Wrench,
} from "lucide-react";
import type { AgentWorkItem, AgentWorkLog as AgentWorkLogData } from "@/api/client";
import { Button } from "@/components/ui/button";
import { assistantToolbarStyle } from "../assistant-ui-config";

interface AgentWorkLogProps {
  work: AgentWorkLogData;
}

function formatDuration(durationMs: number, language: string): string {
  const totalSeconds = Math.max(0.1, durationMs / 1000);
  const isChinese = language.startsWith("zh");
  if (totalSeconds < 60) {
    const seconds = totalSeconds < 10 ? totalSeconds.toFixed(1) : Math.round(totalSeconds);
    return isChinese ? `${seconds} 秒` : `${seconds}s`;
  }
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.round(totalSeconds % 60);
  return isChinese ? `${minutes} 分 ${seconds} 秒` : `${minutes}m ${seconds}s`;
}

function itemStatusIcon(item: AgentWorkItem) {
  if (item.status === "running") {
    return <LoaderCircle className="size-[var(--icon-xs)] animate-spin" />;
  }
  if (item.status === "failed") {
    return <CircleAlert className="size-[var(--icon-xs)] text-destructive" />;
  }
  if (item.status === "pending_approval") {
    return <CircleAlert className="size-[var(--icon-xs)] text-primary" />;
  }
  return <CheckCircle2 className="size-[var(--icon-xs)]" />;
}

function WorkItem({ item }: { item: AgentWorkItem }) {
  const { t } = useTranslation();

  if (item.kind === "reasoning") {
    return (
      <div className="flex gap-2 text-caption text-muted-foreground">
        <Brain className="mt-0.5 size-[var(--icon-xs)] shrink-0" />
        <span className="whitespace-pre-wrap text-foreground/85">{item.content}</span>
      </div>
    );
  }

  return (
    <div className="text-caption text-muted-foreground">
      <div className="flex items-center gap-2">
        <span className="shrink-0">{itemStatusIcon(item)}</span>
        <Wrench className="size-[var(--icon-xs)] shrink-0" />
        <span>{t("assistant.work.usedTool")}</span>
        <code className="rounded bg-muted px-1.5 py-0.5 text-micro text-foreground">
          {item.tool_name || item.title}
        </code>
      </div>
      {(item.input || item.output) && (
        <details className="ml-10 mt-1.5">
          <summary className="cursor-pointer select-none text-micro hover:text-foreground">
            {t("assistant.work.details")}
          </summary>
          <div className="mt-1.5 grid gap-2">
            {item.input && (
              <div>
                <div className="mb-1 text-micro">{t("assistant.work.input")}</div>
                <pre className="max-h-32 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted/60 px-2.5 py-2 text-micro text-foreground/80">
                  {item.input}
                </pre>
              </div>
            )}
            {item.output && (
              <div>
                <div className="mb-1 text-micro">{t("assistant.work.output")}</div>
                <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted/60 px-2.5 py-2 text-micro text-foreground/80">
                  {item.output}
                </pre>
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

export function AgentWorkLog({ work }: AgentWorkLogProps) {
  const { t, i18n } = useTranslation();
  const [expanded, setExpanded] = useState(
    work.status === "running" || work.status === "interrupted",
  );
  const previousStatus = useRef(work.status);

  useEffect(() => {
    if (
      previousStatus.current !== work.status
      && (work.status === "completed" || work.status === "error" || work.status === "expired")
    ) {
      setExpanded(false);
    }
    previousStatus.current = work.status;
  }, [work.status]);

  const running = work.status === "running";
  const title = running
    ? t("assistant.work.thinking")
    : work.status === "interrupted"
      ? t("assistant.work.awaitingApproval")
      : work.status === "expired"
        ? t("assistant.work.expired")
      : work.status === "error"
        ? t("assistant.work.failed")
        : t("assistant.work.workedFor", {
            duration: formatDuration(
              work.duration_ms,
              i18n.resolvedLanguage || i18n.language,
            ),
          });

  return (
    <div className="mb-2 w-full">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="-ml-2 h-8 w-auto gap-1.5 px-2 text-caption font-normal text-muted-foreground hover:bg-transparent hover:text-foreground"
        style={assistantToolbarStyle}
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
      >
        {running ? (
          <LoaderCircle className="size-[var(--icon-xs)] animate-spin" />
        ) : expanded ? (
          <ChevronDown className="size-[var(--icon-xs)]" />
        ) : (
          <ChevronRight className="size-[var(--icon-xs)]" />
        )}
        <span>{title}</span>
      </Button>

      {expanded && (
        <div className="ml-1.5 border-l border-border py-2 pl-4">
          {work.items.length > 0 ? (
            <div className="grid gap-3">
              {work.items.map((item) => <WorkItem key={item.id} item={item} />)}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-caption text-muted-foreground">
              <Brain className="size-[var(--icon-xs)]" />
              <span>{t(running ? "assistant.work.analyzing" : "assistant.work.analyzed")}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
