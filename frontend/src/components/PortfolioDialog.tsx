import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { ChevronDown } from "lucide-react";
import {
  DEFAULT_CURRENCY_OPTIONS,
  portfolioFormControlSizes,
  portfolioToolbarControlSizes,
} from "@/pages/portfolio-ui-config";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import type { Portfolio } from "@/api/client";

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  mode: "create" | "edit";
  portfolio?: Portfolio | null;
  onSubmit: (payload: { name: string; currency: string }) => Promise<void>;
  onDelete?: () => Promise<void>;
}

const control = {
  fontSize: portfolioFormControlSizes.fontSize,
  fontWeight: portfolioFormControlSizes.fontWeight,
} as const;

const btn = {
  fontSize: portfolioToolbarControlSizes.fontSize,
  fontWeight: portfolioToolbarControlSizes.fontWeight,
} as const;

export default function PortfolioDialog({
  open, onOpenChange, mode, portfolio, onSubmit, onDelete,
}: Props) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [currency, setCurrency] = useState("CNY");
  const [curOpen, setCurOpen] = useState(false);
  const [curQuery, setCurQuery] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(portfolio?.name ?? "");
    setCurrency(portfolio?.currency ?? "CNY");
  }, [open, portfolio]);

  const handleSubmit = async () => {
    if (!name.trim() || !currency.trim()) return;
    setSaving(true);
    try {
      await onSubmit({ name: name.trim(), currency: currency.trim().toUpperCase() });
      onOpenChange(false);
    } finally {
      setSaving(false);
    }
  };

  const labelClass = portfolioFormControlSizes.labelTextClassName;
  const placeholderClass = portfolioFormControlSizes.inputPlaceholderClassName;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[420px]" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle className="text-subheading font-medium">
              {mode === "edit" ? t("portfolio.editPortfolio") : t("portfolio.newPortfolio")}
            </DialogTitle>
          </DialogHeader>

          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>{t("portfolio.portfolioName")}</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={`h-8 ${placeholderClass}`}
                style={control}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>{t("portfolio.portfolioCurrency")}</label>
              <Popover open={curOpen} onOpenChange={setCurOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    size={portfolioFormControlSizes.input as "sm"}
                    style={control}
                    className="justify-between h-8 font-normal"
                  >
                    <span className="tabular-nums">{currency}</span>
                    <ChevronDown className="opacity-50 size-[var(--icon-xs)]" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="p-0 w-[200px]" align="start">
                  <Command>
                    <CommandInput
                      value={curQuery}
                      onValueChange={setCurQuery}
                      placeholder={t("portfolio.portfolioCurrency")}
                      className={placeholderClass}
                      style={control}
                    />
                    <CommandList>
                      <CommandEmpty>
                        {curQuery.trim() ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="w-full justify-start"
                            style={btn}
                            onClick={() => {
                              setCurrency(curQuery.trim().toUpperCase());
                              setCurOpen(false);
                              setCurQuery("");
                            }}
                          >
                            {curQuery.trim().toUpperCase()}
                          </Button>
                        ) : (
                          <span className="text-caption text-muted-foreground">—</span>
                        )}
                      </CommandEmpty>
                      <CommandGroup>
                        {DEFAULT_CURRENCY_OPTIONS.map((c) => (
                          <CommandItem
                            key={c}
                            value={c}
                            onSelect={() => {
                              setCurrency(c);
                              setCurOpen(false);
                            }}
                          >
                            <span className="text-ui tabular-nums">{c}</span>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>
          </div>

          <DialogFooter className="flex justify-between sm:justify-between">
            {mode === "edit" && onDelete ? (
              <Button
                variant="outline"
                size={portfolioToolbarControlSizes.primaryAction}
                style={{ ...btn, color: "var(--danger)" }}
                onClick={() => setConfirmDelete(true)}
              >
                {t("portfolio.deletePortfolio")}
              </Button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <Button
                variant="outline"
                size={portfolioToolbarControlSizes.primaryAction}
                style={btn}
                onClick={() => onOpenChange(false)}
              >
                {t("portfolio.cancel")}
              </Button>
              <Button
                size={portfolioToolbarControlSizes.primaryAction}
                style={btn}
                onClick={handleSubmit}
                disabled={saving}
              >
                {t("portfolio.save")}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {onDelete && (
        <ConfirmDialog
          open={confirmDelete}
          onOpenChange={setConfirmDelete}
          title={t("portfolio.confirmDeletePortfolioTitle", { name: portfolio?.name ?? "" })}
          description={t("portfolio.confirmDeletePortfolioBody", {
            count: portfolio?.entry_count ?? 0,
          })}
          confirmLabel={t("portfolio.deletePortfolio")}
          onConfirm={async () => {
            await onDelete();
            setConfirmDelete(false);
            onOpenChange(false);
          }}
        />
      )}
    </>
  );
}
