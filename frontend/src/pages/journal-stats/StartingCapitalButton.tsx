import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { journalStatsControlSizes } from "@/pages/journal-ui-config";
import { useJournalSettings } from "@/journal/journal-settings-context";

interface Props {
  startingCapital: number | null | undefined;
  onChange: (value: number | null) => Promise<void>;
}

export default function StartingCapitalButton({ startingCapital, onChange }: Props) {
  const { t } = useTranslation();
  const { currencyCode, displayMoney } = useJournalSettings();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setDraft(startingCapital == null ? "" : String(startingCapital));
    }
  }, [open, startingCapital]);

  const isSet = startingCapital != null;
  const label = isSet ? displayMoney(startingCapital) : t("journal.startingCapital.set");

  const handleSave = async () => {
    const cleaned = draft.replace(/,/g, "").trim();
    if (cleaned === "") return;
    const parsed = Number(cleaned);
    if (!Number.isFinite(parsed) || parsed < 0) return;
    setSaving(true);
    try {
      await onChange(parsed);
      setOpen(false);
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    setSaving(true);
    try {
      await onChange(null);
      setOpen(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          style={{
            fontSize: journalStatsControlSizes.fontSize,
            fontWeight: journalStatsControlSizes.fontWeight,
          }}
        >
          <Wallet className="size-[var(--icon-sm)]" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64" align="end">
        <div className="flex flex-col gap-3">
          <div className="text-caption text-muted-foreground">
            {t("journal.startingCapital.label")}{currencyCode ? ` (${currencyCode})` : ""}
          </div>
          <Input
            type="text"
            inputMode="decimal"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="50000"
            style={{ fontSize: "var(--font-ui)" }}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSave();
            }}
          />
          <div className="flex justify-between gap-2">
            <Button
              variant="ghost"
              size="xs"
              onClick={handleClear}
              disabled={!isSet || saving}
              style={{ fontSize: "var(--font-ui)" }}
            >
              {t("journal.startingCapital.clear")}
            </Button>
            <Button
              size="xs"
              onClick={handleSave}
              disabled={saving || draft.trim() === ""}
              style={{ fontSize: "var(--font-ui)" }}
            >
              {t("journal.startingCapital.save")}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
