import { CheckCircle2, CircleHelp, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ComplianceSummary } from "@/api/client";

export default function ComplianceSummaryCard({ summary }: { summary: ComplianceSummary }) {
  const { t } = useTranslation();

  return (
    <Card className="gap-2 rounded-lg py-3 shadow-none">
      <CardHeader className="flex flex-row items-center justify-between px-3">
        <CardTitle>{t("compliance.title")}</CardTitle>
        <Badge variant="outline">
          {summary.score == null ? t("compliance.noApplicable") : `${summary.score}%`}
        </Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 px-3">
        {summary.results.length === 0 ? (
          <p className="text-caption text-muted-foreground">{t("compliance.noRules")}</p>
        ) : summary.results.map((result) => {
          const Icon = result.status === "passed"
            ? CheckCircle2
            : result.status === "failed" ? XCircle : CircleHelp;
          return (
            <div key={result.rule_id ?? result.rule_name} className="flex items-center gap-2 text-caption">
              <Icon className={cn(
                "size-[var(--icon-sm)] shrink-0",
                result.status === "passed" && "text-[var(--success)]",
                result.status === "failed" && "text-[var(--danger)]",
                result.status === "not_applicable" && "text-muted-foreground",
              )} />
              <span className="min-w-0 flex-1 truncate">{result.rule_name}</span>
              {result.detail ? <span className="tabular-nums text-muted-foreground">{result.detail}</span> : null}
              <span className="text-muted-foreground">{t(`compliance.status.${result.status}`)}</span>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
