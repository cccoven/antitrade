import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { Banknote } from "lucide-react";
import type { JournalCurrencyCode } from "@/api/client";
import { useAuth } from "@/auth/auth-context";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { JOURNAL_CURRENCY_OPTIONS } from "@/journal/journal-currency";
import { useJournalSettings } from "@/journal/journal-settings-context";

const controlStyle = { fontSize: "var(--font-ui)" };

export default function JournalCurrencyPrompt() {
  const { t, i18n } = useTranslation();
  const { pathname } = useLocation();
  const { user } = useAuth();
  const { currencyCode, loaded, setCurrencyCode } = useJournalSettings();
  const [draft, setDraft] = useState<JournalCurrencyCode>("CNY");
  const [saving, setSaving] = useState(false);
  const open = Boolean(user && pathname.startsWith("/journal") && loaded && !currencyCode);

  useEffect(() => {
    if (open) setDraft(i18n.language.startsWith("zh") ? "CNY" : "USD");
  }, [i18n.language, open]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await setCurrencyCode(draft);
    } catch {
      // API client already shows the user-facing error.
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent
        showCloseButton={false}
        className="sm:max-w-[420px]"
        onEscapeKeyDown={(event) => event.preventDefault()}
        onPointerDownOutside={(event) => event.preventDefault()}
      >
        <DialogHeader>
          <div className="mb-1 flex size-9 items-center justify-center rounded-[10px] bg-muted text-muted-foreground">
            <Banknote className="size-[var(--icon-sm)]" />
          </div>
          <DialogTitle className="text-subheading">{t("journal.currency.promptTitle")}</DialogTitle>
          <DialogDescription className="text-ui">
            {t("journal.currency.promptDescription")}
          </DialogDescription>
        </DialogHeader>
        <Select value={draft} onValueChange={(value) => setDraft(value as JournalCurrencyCode)}>
          <SelectTrigger style={controlStyle}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {JOURNAL_CURRENCY_OPTIONS.map((option) => (
              <SelectItem key={option.code} value={option.code}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="text-caption text-muted-foreground">
          {t("journal.currency.noConversion")}
        </div>
        <DialogFooter>
          <Button size="sm" style={controlStyle} disabled={saving} onClick={handleSave}>
            {t("journal.currency.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
