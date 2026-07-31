import { useTranslation } from "react-i18next";
import {
  Play, Pause, ChevronLeft, ChevronRight,
  SkipBack, SkipForward, Flag,
} from "lucide-react";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import {
  Select, SelectContent, SelectGroup, SelectItem,
  SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  REPLAY_INTERVAL_OPTIONS,
  REPLAY_WINDOW_OPTIONS,
  REPLAY_SPEED_OPTIONS,
  replayControlSizes,
  replayPageStyles,
} from "@/pages/replay-ui-config";

interface ReplayControlsProps {
  disabled?: boolean;
  isPlaying: boolean;
  onTogglePlay: () => void;
  onPrevBar: () => void;
  onNextBar: () => void;
  onJumpToEntry: () => void;
  onJumpToExit: () => void;
  onJumpToEnd: () => void;
  hasExit: boolean;
  speed: number;
  onSpeedChange: (n: number) => void;
  interval: string;
  onIntervalChange: (v: string) => void;
  window: "compact" | "standard" | "full";
  onWindowChange: (v: "compact" | "standard" | "full") => void;
  dataSource?: string | null;
}

export default function ReplayControls(props: ReplayControlsProps) {
  const { t } = useTranslation();
  const {
    isPlaying, onTogglePlay, onPrevBar, onNextBar,
    onJumpToEntry, onJumpToExit, onJumpToEnd, hasExit,
    speed, onSpeedChange, interval, onIntervalChange,
    window: win, onWindowChange, dataSource, disabled = false,
  } = props;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <TooltipIconButton
        label={t("replay.prevBar")}
        variant="outline" size={replayControlSizes.iconAction}
        onClick={onPrevBar} disabled={disabled}
      ><ChevronLeft /></TooltipIconButton>

      <TooltipIconButton
        label={isPlaying ? t("replay.pause") : t("replay.play")}
        size={replayControlSizes.iconAction}
        onClick={onTogglePlay} disabled={disabled}
      >{isPlaying ? <Pause /> : <Play />}</TooltipIconButton>

      <TooltipIconButton
        label={t("replay.nextBar")}
        variant="outline" size={replayControlSizes.iconAction}
        onClick={onNextBar} disabled={disabled}
      ><ChevronRight /></TooltipIconButton>

      <TooltipIconButton
        label={t("replay.jumpToEntry")}
        variant="outline" size={replayControlSizes.iconAction}
        onClick={onJumpToEntry} disabled={disabled}
      ><Flag /></TooltipIconButton>

      <TooltipIconButton
        label={t("replay.jumpToExit")}
        variant="outline" size={replayControlSizes.iconAction}
        onClick={onJumpToExit} disabled={disabled || !hasExit}
      ><SkipForward /></TooltipIconButton>

      <TooltipIconButton
        label={t("replay.jumpToEnd")}
        variant="outline" size={replayControlSizes.iconAction}
        onClick={onJumpToEnd} disabled={disabled}
      ><SkipBack className="rotate-180" /></TooltipIconButton>

      <span className="ml-2 text-caption text-muted-foreground">{t("replay.speed")}</span>
      <ToggleGroup
        type="single"
        size={replayControlSizes.toggle}
        value={String(speed)}
        disabled={disabled}
        onValueChange={(v) => v && onSpeedChange(Number(v))}
      >
        {REPLAY_SPEED_OPTIONS.map((s) => (
          <ToggleGroupItem key={s} value={String(s)} style={replayPageStyles.btnStyle}>
            {s}x
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      <span className="ml-2 text-caption text-muted-foreground">{t("replay.intervalLabel")}</span>
      <Select value={interval} onValueChange={onIntervalChange} disabled={disabled}>
        <SelectTrigger size={replayControlSizes.select} className="w-[120px]" style={replayPageStyles.inputStyle}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {REPLAY_INTERVAL_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>{t(opt.key)}</SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>

      <span className="ml-2 text-caption text-muted-foreground">{t("replay.windowLabel")}</span>
      <ToggleGroup
        type="single"
        size={replayControlSizes.toggle}
        value={win}
        disabled={disabled}
        onValueChange={(v) => {
          if (v === "compact" || v === "standard" || v === "full") onWindowChange(v);
        }}
      >
        {REPLAY_WINDOW_OPTIONS.map((opt) => (
          <ToggleGroupItem key={opt.value} value={opt.value} style={replayPageStyles.btnStyle}>
            {t(opt.key)}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      {dataSource && (
        <span className="ml-2 text-caption text-muted-foreground">
          {t("replay.dataSource")}: <span className="font-medium uppercase">{dataSource}</span>
        </span>
      )}
    </div>
  );
}
