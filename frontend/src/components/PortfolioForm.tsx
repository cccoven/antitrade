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
import { Textarea } from "@/components/ui/textarea";
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
  portfolioFormControlSizes,
  portfolioInlineTagClassName,
  portfolioToolbarControlSizes,
} from "@/pages/portfolio-ui-config";
import type {
  PortfolioEntry,
  PortfolioCategory,
  CreatePortfolioEntryRequest,
} from "@/api/client";

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  entry: PortfolioEntry | null;
  categories: PortfolioCategory[];
  onSubmit: (payload: CreatePortfolioEntryRequest) => Promise<void>;
  onCreateCategory: (name: string, kind: "asset" | "liability") => Promise<void>;
}

const controlStyle = {
  fontSize: portfolioFormControlSizes.fontSize,
  fontWeight: portfolioFormControlSizes.fontWeight,
} as const;

const btnStyle = {
  fontSize: portfolioToolbarControlSizes.fontSize,
  fontWeight: portfolioToolbarControlSizes.fontWeight,
} as const;

export default function PortfolioForm({
  open,
  onOpenChange,
  entry,
  categories,
  onSubmit,
  onCreateCategory,
}: Props) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [platform, setPlatform] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [catOpen, setCatOpen] = useState(false);
  const [catQuery, setCatQuery] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(entry?.name ?? "");
    setCategory(entry?.category ?? "");
    setPlatform(entry?.platform ?? "");
    setAmount(entry ? String(entry.amount) : "");
    setNotes(entry?.notes ?? "");
  }, [open, entry]);

  const handleSubmit = async () => {
    if (!name.trim() || !category.trim()) return;
    const numAmount = Number(amount);
    if (!Number.isFinite(numAmount) || numAmount < 0) return;
    setSaving(true);
    try {
      await onSubmit({
        name: name.trim(),
        category: category.trim(),
        platform: platform.trim() || null,
        amount: numAmount,
        notes: notes.trim(),
      });
      onOpenChange(false);
    } finally {
      setSaving(false);
    }
  };

  const labelClass = portfolioFormControlSizes.labelTextClassName;
  const placeholderClass = portfolioFormControlSizes.inputPlaceholderClassName;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle className="text-subheading font-medium">
            {entry ? t("portfolio.editEntry") : t("portfolio.addEntry")}
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>{t("portfolio.name")}</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("portfolio.placeholderName")}
              className={`h-8 ${placeholderClass}`}
              style={controlStyle}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>{t("portfolio.category")}</label>
              <Popover open={catOpen} onOpenChange={setCatOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    size={portfolioFormControlSizes.input as "sm"}
                    style={controlStyle}
                    className="justify-between h-8 font-normal"
                  >
                    {category || (
                      <span className="text-muted-foreground text-[length:var(--font-caption)]">
                        {t("portfolio.category")}
                      </span>
                    )}
                    <ChevronDown className="opacity-50 size-[var(--icon-xs)]" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="p-0 w-[240px]" align="start">
                  <Command>
                    <CommandInput
                      value={catQuery}
                      onValueChange={setCatQuery}
                      placeholder={t("portfolio.category")}
                    />
                    <CommandList>
                      <CommandEmpty>
                        {catQuery.trim() ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="w-full justify-start"
                            style={btnStyle}
                            onClick={async () => {
                              await onCreateCategory(catQuery.trim(), "asset");
                              setCategory(catQuery.trim());
                              setCatOpen(false);
                              setCatQuery("");
                            }}
                          >
                            {t("portfolio.categoryCreate", {
                              name: catQuery.trim(),
                            })}
                          </Button>
                        ) : (
                          <span className="text-caption text-muted-foreground">
                            —
                          </span>
                        )}
                      </CommandEmpty>
                      <CommandGroup>
                        {categories.map((c) => (
                          <CommandItem
                            key={c.id}
                            value={c.name}
                            onSelect={() => {
                              setCategory(c.name);
                              setCatOpen(false);
                            }}
                          >
                            <span className="text-ui">{c.name}</span>
                            {c.kind === "liability" && (
                              <span className={portfolioInlineTagClassName}>
                                · {t("portfolio.liability")}
                              </span>
                            )}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>{t("portfolio.platform")}</label>
              <Input
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                placeholder={t("portfolio.placeholderPlatform")}
                className={`h-8 ${placeholderClass}`}
                style={controlStyle}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>{t("portfolio.amount")}</label>
            <Input
              type="number"
              inputMode="decimal"
              min="0"
              step="any"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder={t("portfolio.placeholderAmount")}
              className={`h-8 tabular-nums ${placeholderClass}`}
              style={controlStyle}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>{t("portfolio.notes")}</label>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t("portfolio.placeholderNotes")}
              rows={portfolioFormControlSizes.textareaRows}
              className={placeholderClass}
              style={controlStyle}
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            size={portfolioToolbarControlSizes.primaryAction}
            style={btnStyle}
            onClick={() => onOpenChange(false)}
          >
            {t("portfolio.cancel")}
          </Button>
          <Button
            size={portfolioToolbarControlSizes.primaryAction}
            style={btnStyle}
            onClick={handleSubmit}
            disabled={saving}
          >
            {t("portfolio.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
