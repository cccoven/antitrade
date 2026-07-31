import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  BellOff,
  BellRing,
  Binoculars,
  ChartNoAxesCombined,
  CircleCheck,
  CircleOff,
  CirclePause,
  Clock3,
  FileText,
  Newspaper,
  Pause,
  Pencil,
  Play,
  Plus,
  Radar,
  RefreshCw,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import LoginRequiredPage from "@/auth/LoginRequiredPage";
import { useAuth } from "@/auth/auth-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import FlushPage from "@/components/FlushPage";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  createAutomationTask,
  deleteAutomationTask,
  listAgentFindings,
  listAgentReports,
  listAutomationTasks,
  patchAutomationTask,
  runAutomationTask,
  type AgentFinding,
  type AgentReport,
  type AutomationTask,
  type AutomationTaskType,
  type FindingSeverity,
} from "@/api/automations";
import {
  listNotificationChannels,
  type NotificationChannel,
} from "@/api/client";
import { automationsUi, automationTimezones } from "./automations-ui-config";

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : "—";
}

function severityClassName(severity: FindingSeverity) {
  if (severity === "critical") {
    return "border-red-500/35 bg-red-500/10 text-red-600 dark:text-red-400";
  }
  if (severity === "warning") {
    return "border-amber-500/35 bg-amber-500/10 text-amber-600 dark:text-amber-400";
  }
  return "border-sky-500/35 bg-sky-500/10 text-sky-600 dark:text-sky-400";
}

function taskTypeIcon(taskType: AutomationTaskType) {
  if (taskType === "risk_guardian") {
    return <ShieldAlert className="size-[var(--icon-sm)]" />;
  }
  if (taskType === "news_impact") {
    return <Newspaper className="size-[var(--icon-sm)]" />;
  }
  if (taskType === "market_watch") {
    return <Binoculars className="size-[var(--icon-sm)]" />;
  }
  if (taskType === "condition_monitor") {
    return <Radar className="size-[var(--icon-sm)]" />;
  }
  if (taskType === "session_report") {
    return <FileText className="size-[var(--icon-sm)]" />;
  }
  return <ChartNoAxesCombined className="size-[var(--icon-sm)]" />;
}

export default function AutomationsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const [tasks, setTasks] = useState<AutomationTask[]>([]);
  const [findings, setFindings] = useState<AgentFinding[]>([]);
  const [reports, setReports] = useState<AgentReport[]>([]);
  const [channels, setChannels] = useState<NotificationChannel[]>([]);
  const [findingView, setFindingView] = useState<"active" | "history">("active");
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<AutomationTask | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AutomationTask | null>(null);
  const [name, setName] = useState("");
  const [taskType, setTaskType] = useState<AutomationTaskType>("risk_guardian");
  const [scheduleKind, setScheduleKind] = useState<"interval" | "daily">("daily");
  const [scheduleValue, setScheduleValue] = useState("08:30");
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
  );
  const [symbols, setSymbols] = useState("");
  const [marketInterval, setMarketInterval] = useState<
    "5min" | "15min" | "1h" | "4h" | "1day"
  >("1h");
  const [conditionKind, setConditionKind] = useState<
    "percent_change" | "price_above" | "price_below"
  >("percent_change");
  const [threshold, setThreshold] = useState("1");
  const [proximityPercent, setProximityPercent] = useState("0.5");
  const [analysisInstruction, setAnalysisInstruction] = useState("");
  const [minSeverity, setMinSeverity] = useState<FindingSeverity>("warning");
  const [selectedChannelId, setSelectedChannelId] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [taskRows, activeRows, historyRows, reportRows, channelRows] = await Promise.all([
        listAutomationTasks(),
        listAgentFindings({ status: "open", limit: 200 }),
        listAgentFindings({ status: "resolved", limit: 200 }),
        listAgentReports({ limit: 100 }),
        listNotificationChannels(),
      ]);
      setTasks(taskRows);
      setFindings([...activeRows, ...historyRows]);
      setReports(reportRows);
      setChannels(channelRows);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) void refresh();
  }, [refresh, user]);

  const counts = useMemo(() => ({
    active: tasks.filter((item) => item.status === "active").length,
    critical: findings.filter(
      (item) => item.status === "open" && item.severity === "critical",
    ).length,
    open: findings.filter((item) => item.status === "open").length,
  }), [findings, tasks]);
  const activeChannels = useMemo(
    () => channels.filter((channel) => channel.status === "active"),
    [channels],
  );
  const activeFindings = useMemo(
    () => findings.filter((finding) => finding.status === "open"),
    [findings],
  );
  const historyFindings = useMemo(
    () => findings.filter((finding) => finding.status === "resolved"),
    [findings],
  );
  const visibleFindings = findingView === "active" ? activeFindings : historyFindings;
  const draftInvalid = (
    ["market_watch", "condition_monitor"].includes(taskType) && !symbols.trim()
  ) || (
    taskType === "condition_monitor" && Number(threshold) <= 0
  ) || (
    taskType === "plan_guardian"
    && (Number(proximityPercent) <= 0 || Number(proximityPercent) > 10)
  ) || (
    analysisInstruction.length > 1000
  );
  const availableTimezones = useMemo(
    () => automationTimezones.includes(timezone)
      ? automationTimezones
      : [timezone, ...automationTimezones],
    [timezone],
  );

  const resetDraft = () => {
    setEditingTask(null);
    setName("");
    setTaskType("risk_guardian");
    setScheduleKind("daily");
    setScheduleValue("08:30");
    setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai");
    setSymbols("");
    setMarketInterval("1h");
    setConditionKind("percent_change");
    setThreshold("1");
    setProximityPercent("0.5");
    setAnalysisInstruction("");
    setMinSeverity("warning");
    setSelectedChannelId("");
  };

  const openCreateDialog = () => {
    resetDraft();
    setDialogOpen(true);
  };

  const openEditDialog = (task: AutomationTask) => {
    setEditingTask(task);
    setName(task.name);
    setTaskType(task.task_type);
    setScheduleKind(task.schedule_kind);
    setScheduleValue(
      task.schedule_kind === "daily"
        ? String(task.schedule_config.time ?? "08:30")
        : String(task.schedule_config.minutes ?? 15),
    );
    setTimezone(task.timezone);
    setSymbols((task.scope.symbols ?? []).join(", "));
    setMarketInterval(task.scope.interval ?? "1h");
    setConditionKind(task.scope.condition_kind ?? "percent_change");
    setThreshold(String(task.scope.threshold ?? 1));
    setProximityPercent(String(task.scope.proximity_percent ?? 0.5));
    setAnalysisInstruction(task.scope.analysis_instruction ?? "");
    setMinSeverity(task.notification_config.min_severity ?? "warning");
    setSelectedChannelId(task.notification_config.channel_id ?? "");
    setDialogOpen(true);
  };

  const handleSave = async () => {
    const displayName = name.trim() || t(`automations.type.${taskType}`);
    const selectedChannel = activeChannels.find(
      (channel) => channel.id === selectedChannelId,
    );
    const draft = {
      name: displayName,
      task_type: taskType,
      schedule_kind: scheduleKind,
      schedule_config: scheduleKind === "daily"
        ? { time: scheduleValue }
        : { minutes: Number(scheduleValue) || 15 },
      timezone,
      scope: {
        symbols: symbols.split(",").map((item) => item.trim()).filter(Boolean),
        interval: marketInterval,
        ...(taskType === "condition_monitor" ? {
          condition_kind: conditionKind,
          threshold: Number(threshold),
        } : {}),
        ...(taskType === "plan_guardian" ? {
          proximity_percent: Number(proximityPercent),
        } : {}),
        ...(["market_watch", "session_report"].includes(taskType) ? {
          analysis_instruction: analysisInstruction.trim(),
        } : {}),
      },
      notification_config: {
        enabled: Boolean(selectedChannel),
        min_severity: minSeverity,
        channel_id: selectedChannel?.id ?? null,
        locale: selectedChannel?.locale ?? "zh",
      },
    };
    if (editingTask) {
      await patchAutomationTask(editingTask.id, draft);
    } else {
      await createAutomationTask(draft);
    }
    setDialogOpen(false);
    resetDraft();
    await refresh();
  };

  if (authLoading) return null;
  if (!user) return <LoginRequiredPage />;

  return (
    <FlushPage
      contentClassName="gap-5 p-5"
      toolbar={
        <div className="title-description-stack">
          <h1 className="text-heading font-semibold text-foreground">
            {t("automations.title")}
          </h1>
          <p className="text-caption text-muted-foreground">
            {t("automations.subtitle")}
          </p>
        </div>
      }
      toolbarAside={
        <div className="flex gap-2">
          <TooltipIconButton
            label={t("automations.refresh")}
            variant="outline"
            size="icon-sm"
            style={automationsUi.buttonStyle}
            onClick={() => void refresh()}
            disabled={loading}
          >
            <RefreshCw className={loading ? "animate-spin" : ""} />
          </TooltipIconButton>
          <TooltipIconButton
            label={t("automations.create")}
            size="icon-sm"
            style={automationsUi.buttonStyle}
            onClick={openCreateDialog}
          >
            <Plus />
          </TooltipIconButton>
        </div>
      }
    >

      <div className="grid gap-3 md:grid-cols-3">
        <Card className="gap-1 py-4">
          <CardContent className="flex items-center gap-3 px-4">
            <Activity className="size-[var(--icon-md)] text-primary" />
            <div>
              <div className="text-heading font-semibold">{counts.active}</div>
              <div className="text-caption text-muted-foreground">
                {t("automations.metric.active")}
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="gap-1 py-4">
          <CardContent className="flex items-center gap-3 px-4">
            <AlertTriangle className="size-[var(--icon-md)] text-[var(--danger)]" />
            <div>
              <div className="text-heading font-semibold">{counts.critical}</div>
              <div className="text-caption text-muted-foreground">
                {t("automations.metric.critical")}
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="gap-1 py-4">
          <CardContent className="flex items-center gap-3 px-4">
            <ShieldAlert className="size-[var(--icon-md)] text-muted-foreground" />
            <div>
              <div className="text-heading font-semibold">{counts.open}</div>
              <div className="text-caption text-muted-foreground">
                {t("automations.metric.open")}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="tasks">
        <TabsList variant="line">
          <TabsTrigger value="tasks" style={automationsUi.buttonStyle}>
            {t("automations.tab.tasks")}
          </TabsTrigger>
          <TabsTrigger value="reports" style={automationsUi.buttonStyle}>
            {t("automations.tab.reports")} · {reports.length}
          </TabsTrigger>
          <TabsTrigger value="findings" style={automationsUi.buttonStyle}>
            {t("automations.tab.findings")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="tasks" className="mt-4 space-y-3">
          {tasks.length === 0 ? (
            <Card><CardContent className="py-10 text-center text-caption text-muted-foreground">
              {t("automations.empty.tasks")}
            </CardContent></Card>
          ) : tasks.map((task) => {
            const notificationChannel = activeChannels.find(
              (channel) => (
                task.notification_config.enabled
                && channel.id === task.notification_config.channel_id
              ),
            );
            const notificationLabel = notificationChannel
              ? t("automations.notification.configured", {
                  channel: notificationChannel.channel_type === "in_app"
                    ? t("notifications.inApp.name")
                    : notificationChannel.name,
                })
              : t("automations.notification.unconfigured");
            const taskStatusLabel = t(`automations.status.${task.status}`);
            return (
            <Card key={task.id} className="gap-0 py-0">
              <CardHeader className="border-b border-border/60 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {taskTypeIcon(task.task_type)}
                    <CardTitle className="text-subheading">{task.name}</CardTitle>
                    <Badge variant="outline">
                      {t(`automations.type.${task.task_type}`)}
                    </Badge>
                    <Badge
                      variant="outline"
                      className={`size-6 justify-center p-0 ${
                        task.status === "active"
                          ? "border-emerald-500/40 text-emerald-600 dark:text-emerald-400"
                          : task.status === "paused"
                            ? "border-amber-500/40 text-amber-600 dark:text-amber-400"
                            : "text-muted-foreground"
                      }`}
                      aria-label={taskStatusLabel}
                      title={taskStatusLabel}
                    >
                      {task.status === "active"
                        ? <CircleCheck className="size-[var(--icon-xs)]" />
                        : task.status === "paused"
                          ? <CirclePause className="size-[var(--icon-xs)]" />
                          : <CircleOff className="size-[var(--icon-xs)]" />}
                    </Badge>
                    <Badge
                      variant="outline"
                      className={`size-6 justify-center p-0 ${notificationChannel
                        ? "border-emerald-500/40 text-emerald-600 dark:text-emerald-400"
                        : "border-amber-500/40 text-amber-600 dark:text-amber-400"}`}
                      aria-label={notificationLabel}
                      title={notificationLabel}
                    >
                      {notificationChannel
                        ? <BellRing className="size-[var(--icon-xs)]" />
                        : <BellOff className="size-[var(--icon-xs)]" />}
                    </Badge>
                  </div>
                  <div className="flex gap-1.5">
                    <TooltipIconButton
                      label={t("automations.runNow")}
                      variant="outline"
                      size="icon-sm"
                      style={automationsUi.buttonStyle}
                      onClick={async () => {
                        await runAutomationTask(task.id);
                        await refresh();
                      }}
                    >
                      <Play />
                    </TooltipIconButton>
                    <TooltipIconButton
                      label={task.status === "active"
                        ? t("automations.pause")
                        : t("automations.resume")}
                      variant="outline"
                      size="icon-sm"
                      style={automationsUi.buttonStyle}
                      onClick={async () => {
                        await patchAutomationTask(task.id, {
                          status: task.status === "active" ? "paused" : "active",
                        });
                        await refresh();
                      }}
                    >
                      {task.status === "active"
                        ? <Pause />
                        : <Clock3 />}
                    </TooltipIconButton>
                    <TooltipIconButton
                      label={t("automations.edit")}
                      variant="outline"
                      size="icon-sm"
                      style={automationsUi.buttonStyle}
                      onClick={() => openEditDialog(task)}
                    >
                      <Pencil />
                    </TooltipIconButton>
                    <TooltipIconButton
                      label={t("automations.delete")}
                      variant="outline"
                      size="icon-sm"
                      style={automationsUi.buttonStyle}
                      className="hover:border-destructive hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => setDeleteTarget(task)}
                    >
                      <Trash2 />
                    </TooltipIconButton>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="grid gap-3 px-4 py-3 text-caption text-muted-foreground md:grid-cols-3">
                <div><Clock3 className="mr-1 inline size-[var(--icon-xs)]" />
                  {t("automations.nextRun")}: {formatTime(task.next_run_at)}
                </div>
                <div>{t("automations.lastRun")}: {formatTime(task.last_run_at)}</div>
                <div>{task.timezone}</div>
              </CardContent>
            </Card>
            );
          })}
        </TabsContent>

        <TabsContent value="reports" className="mt-4 space-y-3">
          {reports.length === 0 ? (
            <Card><CardContent className="py-10 text-center text-caption text-muted-foreground">
              {t("automations.empty.reports")}
            </CardContent></Card>
          ) : reports.map((report) => {
            const summary = i18n.language.startsWith("en")
              ? report.summary_en || report.summary
              : report.summary;
            const marketRows = (report.output.evidence ?? []).filter(
              (item) => item.kind === "market_snapshot",
            );
            return (
              <Card key={report.id} className="gap-0 py-0">
                <CardHeader className="border-b border-border/60 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      {taskTypeIcon(report.task_type)}
                      <CardTitle className="truncate text-subheading">
                        {report.task_name}
                      </CardTitle>
                      <Badge variant="outline">
                        {t(`automations.type.${report.task_type}`)}
                      </Badge>
                      {report.status === "partial" && (
                        <Badge className="border-amber-500/35 bg-amber-500/10 text-amber-600 dark:text-amber-400" variant="outline">
                          {t("automations.report.partial")}
                        </Badge>
                      )}
                    </div>
                    <span className="shrink-0 text-micro text-muted-foreground">
                      {t("automations.report.asOf")}: {formatTime(report.as_of)}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 px-4 py-4">
                  <p className="text-ui text-foreground">{summary}</p>
                  {marketRows.length > 0 && (
                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                      {marketRows.slice(0, 8).map((row, index) => {
                        const price = typeof row.price === "number" ? row.price : null;
                        const change = typeof row.percent_change === "number"
                          ? row.percent_change
                          : null;
                        return (
                          <div
                            key={`${String(row.symbol)}-${index}`}
                            className="rounded-md border border-border/70 bg-muted/20 px-3 py-2"
                          >
                            <div className="text-caption font-medium text-foreground">
                              {String(row.symbol ?? "—")}
                            </div>
                            <div className="mt-1 flex items-baseline justify-between gap-2">
                              <span className="text-ui tabular-nums">
                                {price === null ? "—" : price.toLocaleString()}
                              </span>
                              <span className={`text-micro tabular-nums ${
                                change === null
                                  ? "text-muted-foreground"
                                  : change >= 0
                                    ? "text-emerald-600 dark:text-emerald-400"
                                    : "text-red-600 dark:text-red-400"
                              }`}>
                                {change === null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </TabsContent>

        <TabsContent value="findings" className="mt-4 space-y-3">
          <div className="flex justify-end">
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              value={findingView}
              onValueChange={(value) => {
                if (value) setFindingView(value as "active" | "history");
              }}
            >
              <ToggleGroupItem value="active" style={automationsUi.buttonStyle}>
                {t("automations.findings.active")} · {activeFindings.length}
              </ToggleGroupItem>
              <ToggleGroupItem value="history" style={automationsUi.buttonStyle}>
                {t("automations.findings.history")} · {historyFindings.length}
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
          {visibleFindings.length === 0 ? (
            <Card><CardContent className="py-10 text-center text-caption text-muted-foreground">
              {t(findingView === "active"
                ? "automations.empty.activeFindings"
                : "automations.empty.historyFindings")}
            </CardContent></Card>
          ) : visibleFindings.map((finding) => (
            <Card key={finding.id} className="gap-0 py-0">
              <CardContent className="flex items-start justify-between gap-4 px-4 py-4">
                <div className="min-w-0">
                  <div className="mb-1.5 flex flex-wrap items-center gap-2">
                    <Badge
                      variant="outline"
                      className={severityClassName(finding.severity)}
                    >
                      {t(`automations.severity.${finding.severity}`)}
                    </Badge>
                    {finding.status === "resolved" && (
                      <Badge
                        variant="outline"
                        className="border-emerald-500/35 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                      >
                        {t(finding.finding_type === "news"
                          ? "automations.findingStatus.expired"
                          : "automations.findingStatus.recovered")}
                      </Badge>
                    )}
                    <span className="text-ui font-medium text-foreground">{finding.title}</span>
                  </div>
                  <p className="text-caption text-muted-foreground">{finding.body}</p>
                  <p className="mt-2 text-micro text-muted-foreground">
                    {finding.status === "resolved"
                      ? t("automations.endedAt")
                      : t("automations.asOf")}: {formatTime(
                        finding.resolved_at ?? finding.last_seen_at,
                      )}
                  </p>
                  {finding.finding_type !== "news" && (
                    <p className="mt-1 text-micro text-muted-foreground">
                      {t("automations.recordedDataNotice")}
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>
      </Tabs>

      <Dialog open={dialogOpen} onOpenChange={(open) => {
        setDialogOpen(open);
        if (!open) resetDraft();
      }}>
        <DialogContent showCloseButton={false} className="max-h-[92vh] overflow-y-auto sm:max-w-[760px]">
          <DialogHeader>
            <DialogTitle className="text-subheading font-medium">
              {t(editingTask ? "automations.editTitle" : "automations.createTitle")}
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-x-4 gap-y-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-caption text-muted-foreground">
                {t("automations.form.name")}
              </Label>
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                style={automationsUi.inputStyle}
                placeholder={t(`automations.type.${taskType}`)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-caption text-muted-foreground">
                {t("automations.form.type")}
              </Label>
              <Select
                value={taskType}
                disabled={Boolean(editingTask)}
                onValueChange={(value) => setTaskType(value as AutomationTaskType)}
              >
                <SelectTrigger className="w-full" style={automationsUi.inputStyle}><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="risk_guardian">{t("automations.type.risk_guardian")}</SelectItem>
                  <SelectItem value="news_impact">{t("automations.type.news_impact")}</SelectItem>
                  <SelectItem value="market_watch">{t("automations.type.market_watch")}</SelectItem>
                  <SelectItem value="condition_monitor">{t("automations.type.condition_monitor")}</SelectItem>
                  <SelectItem value="session_report">{t("automations.type.session_report")}</SelectItem>
                  <SelectItem value="plan_guardian">{t("automations.type.plan_guardian")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:col-span-2 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-caption text-muted-foreground">
                  {t("automations.form.schedule")}
                </Label>
                <Select value={scheduleKind} onValueChange={(value) => {
                  const next = value as "interval" | "daily";
                  setScheduleKind(next);
                  setScheduleValue(next === "daily" ? "08:30" : "15");
                }}>
                  <SelectTrigger className="w-full" style={automationsUi.inputStyle}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">{t("automations.schedule.daily")}</SelectItem>
                    <SelectItem value="interval">{t("automations.schedule.interval")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-caption text-muted-foreground">
                  {scheduleKind === "daily"
                    ? t("automations.form.time")
                    : t("automations.form.minutes")}
                </Label>
                <Input
                  type={scheduleKind === "daily" ? "time" : "number"}
                  min={scheduleKind === "interval" ? 15 : undefined}
                  value={scheduleValue}
                  onChange={(event) => setScheduleValue(event.target.value)}
                  style={automationsUi.inputStyle}
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-caption text-muted-foreground">
                {t("automations.form.timezone")}
              </Label>
              <Select value={timezone} onValueChange={setTimezone}>
                <SelectTrigger className="w-full" style={automationsUi.inputStyle}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {availableTimezones.map((item) => (
                    <SelectItem key={item} value={item}>
                      {item}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {["news_impact", "market_watch", "condition_monitor", "session_report"].includes(taskType) && (
              <div className="space-y-1.5">
                <Label className="text-caption text-muted-foreground">
                  {t(taskType === "news_impact"
                    ? "automations.form.symbols"
                    : "automations.form.watchSymbols")}
                </Label>
                <Input value={symbols} onChange={(event) => setSymbols(event.target.value)} style={automationsUi.inputStyle} placeholder="MNQ, AAPL, BTCUSD" />
              </div>
            )}
            {["market_watch", "condition_monitor", "session_report", "plan_guardian"].includes(taskType) && (
              <div className="space-y-1.5">
                <Label className="text-caption text-muted-foreground">
                  {t("automations.form.marketInterval")}
                </Label>
                <Select
                  value={marketInterval}
                  onValueChange={(value) => setMarketInterval(
                    value as "5min" | "15min" | "1h" | "4h" | "1day",
                  )}
                >
                  <SelectTrigger className="w-full" style={automationsUi.inputStyle}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(["5min", "15min", "1h", "4h", "1day"] as const).map((interval) => (
                      <SelectItem key={interval} value={interval}>
                        {t(`automations.marketInterval.${interval}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {taskType === "condition_monitor" && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-caption text-muted-foreground">
                    {t("automations.form.condition")}
                  </Label>
                  <Select
                    value={conditionKind}
                    onValueChange={(value) => setConditionKind(
                      value as "percent_change" | "price_above" | "price_below",
                    )}
                  >
                    <SelectTrigger className="w-full" style={automationsUi.inputStyle}><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="percent_change">{t("automations.condition.percent_change")}</SelectItem>
                      <SelectItem value="price_above">{t("automations.condition.price_above")}</SelectItem>
                      <SelectItem value="price_below">{t("automations.condition.price_below")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-caption text-muted-foreground">
                    {t("automations.form.threshold")}
                  </Label>
                  <Input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={threshold}
                    onChange={(event) => setThreshold(event.target.value)}
                    style={automationsUi.inputStyle}
                  />
                </div>
              </div>
            )}
            {taskType === "plan_guardian" && (
              <div className="space-y-1.5">
                <Label className="text-caption text-muted-foreground">
                  {t("automations.form.proximity")}
                </Label>
                <Input
                  type="number"
                  min="0.1"
                  max="10"
                  step="0.1"
                  value={proximityPercent}
                  onChange={(event) => setProximityPercent(event.target.value)}
                  style={automationsUi.inputStyle}
                />
              </div>
            )}
            <div className="space-y-1.5">
              <Label className="text-caption text-muted-foreground">
                {t("automations.form.channel")}
              </Label>
              {activeChannels.length === 0 ? (
                <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
                  <div className="flex items-center gap-2 text-caption text-muted-foreground">
                    <BellOff className="size-[var(--icon-sm)]" />
                    {t("automations.notification.connectHint")}
                  </div>
                  <Button
                    className="mt-2"
                    variant="outline"
                    size="sm"
                    style={automationsUi.buttonStyle}
                    onClick={() => navigate("/settings?section=notifications")}
                  >
                    {t("automations.notification.goToSettings")}
                  </Button>
                </div>
              ) : (
                <>
                  <Select
                    value={activeChannels.some(
                      (channel) => channel.id === selectedChannelId,
                    ) ? selectedChannelId : "__none__"}
                    onValueChange={(value) => {
                      setSelectedChannelId(value === "__none__" ? "" : value);
                    }}
                  >
                    <SelectTrigger className="w-full" style={automationsUi.inputStyle}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">
                        {t("automations.notification.inAppOnly")}
                      </SelectItem>
                      {activeChannels.map((channel) => (
                        <SelectItem key={channel.id} value={channel.id}>
                          {channel.channel_type === "in_app"
                            ? t("notifications.inApp.name")
                            : `${channel.name} · ${
                                channel.channel_type === "telegram"
                                  ? "Telegram"
                                  : channel.channel_type === "discord"
                                    ? "Discord"
                                    : t("automations.notification.demoChannel")
                              }`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {!activeChannels.some(
                    (channel) => channel.id === selectedChannelId,
                  ) && (
                    <p className="text-caption text-muted-foreground">
                      {t("automations.notification.inAppHint")}
                    </p>
                  )}
                </>
              )}
            </div>
            {!["market_watch", "session_report"].includes(taskType) && (
              <div className="space-y-1.5">
                <Label className="text-caption text-muted-foreground">
                  {t("automations.form.minSeverity")}
                </Label>
                <Select value={minSeverity} onValueChange={(value) => setMinSeverity(value as FindingSeverity)}>
                  <SelectTrigger className="w-full" style={automationsUi.inputStyle}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="info">{t("automations.severity.info")}</SelectItem>
                    <SelectItem value="warning">{t("automations.severity.warning")}</SelectItem>
                    <SelectItem value="critical">{t("automations.severity.critical")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            {["market_watch", "session_report"].includes(taskType) && (
              <div className="space-y-1.5 sm:col-span-2">
                <Label className="text-caption text-muted-foreground">
                  {t("automations.form.analysisInstruction")}
                </Label>
                <Textarea
                  value={analysisInstruction}
                  onChange={(event) => setAnalysisInstruction(event.target.value)}
                  maxLength={1000}
                  rows={3}
                  style={automationsUi.inputStyle}
                  placeholder={t("automations.form.analysisInstructionPlaceholder")}
                />
                <p className="text-micro text-muted-foreground">
                  {t("automations.form.analysisInstructionHint")}
                </p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" style={automationsUi.buttonStyle} onClick={() => {
              setDialogOpen(false);
              resetDraft();
            }}>
              {t("common.cancel")}
            </Button>
            <Button
              size="sm"
              style={automationsUi.buttonStyle}
              disabled={draftInvalid}
              onClick={() => void handleSave()}
            >
              {t(editingTask ? "automations.save" : "automations.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
        title={t("automations.deleteTitle")}
        description={t("automations.deleteDescription", {
          name: deleteTarget?.name ?? "",
        })}
        confirmLabel={t("automations.delete")}
        onConfirm={() => {
          if (!deleteTarget) return;
          void deleteAutomationTask(deleteTarget.id).then(async () => {
            setDeleteTarget(null);
            await refresh();
          });
        }}
      />
    </FlushPage>
  );
}
