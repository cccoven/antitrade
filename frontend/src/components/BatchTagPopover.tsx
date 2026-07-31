import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { PlusIcon, CheckIcon } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface BatchTagPopoverProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existingTags?: string[];
  onConfirm: (tags: string[]) => void;
  trigger: React.ReactNode;
  triggerTooltip?: string;
}

const UI_STYLE = { fontSize: "var(--font-ui)" };

export default function BatchTagPopover({
  open,
  onOpenChange,
  existingTags = [],
  onConfirm,
  trigger,
  triggerTooltip,
}: BatchTagPopoverProps) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [input, setInput] = useState("");

  useEffect(() => {
    if (!open) {
      setSelected(new Set());
      setInput("");
    }
  }, [open]);

  const matchedExisting = existingTags.filter((tag) =>
    tag.toLowerCase().includes(input.toLowerCase()),
  );
  const exactHit = existingTags.some(
    (tag) => tag.toLowerCase() === input.toLowerCase(),
  );
  const canCreate = input.trim() !== "" && !exactHit;

  const toggle = (tag: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(tag)) next.delete(tag);
      else next.add(tag);
      return next;
    });
  };

  const create = () => {
    const v = input.trim();
    if (!v) return;
    toggle(v);
    setInput("");
  };

  const handleConfirm = () => {
    onConfirm(Array.from(selected));
  };

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      {triggerTooltip ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <PopoverTrigger asChild>{trigger}</PopoverTrigger>
          </TooltipTrigger>
          <TooltipContent side="bottom">{triggerTooltip}</TooltipContent>
        </Tooltip>
      ) : (
        <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      )}
      <PopoverContent className="w-[280px] p-0" align="start">
        <Command>
          <CommandInput
            value={input}
            onValueChange={setInput}
            placeholder={t("journal.batch.tagPopoverPlaceholder")}
            style={UI_STYLE}
          />
          <CommandList>
            <CommandEmpty>
              {canCreate ? null : t("journal.batch.tagEmpty")}
            </CommandEmpty>
            {matchedExisting.length > 0 && (
              <CommandGroup>
                {matchedExisting.map((tag) => {
                  const checked = selected.has(tag);
                  return (
                    <CommandItem
                      key={tag}
                      value={tag}
                      onSelect={() => toggle(tag)}
                      style={UI_STYLE}
                    >
                      <CheckIcon
                        className={cn(
                          "mr-2 size-4",
                          checked ? "opacity-100" : "opacity-0",
                        )}
                      />
                      {tag}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            )}
            {canCreate && (
              <CommandGroup>
                <CommandItem value={`__create__${input}`} onSelect={create} style={UI_STYLE}>
                  <PlusIcon className="mr-2 size-4" />
                  {t("journal.batch.tagPopoverCreate", { value: input })}
                </CommandItem>
              </CommandGroup>
            )}
          </CommandList>
        </Command>
        {selected.size > 0 && (
          <div className="flex flex-wrap gap-1 border-t border-border px-2 py-2">
            {Array.from(selected).map((tag) => (
              <span
                key={tag}
                className="rounded bg-muted px-2 py-0.5 text-caption"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
        <div className="flex items-center justify-end gap-2 border-t border-border px-2 py-1.5">
          <Button
            size="xs"
            style={UI_STYLE}
            disabled={selected.size === 0}
            onClick={handleConfirm}
          >
            {t("journal.batch.tagPopoverAdd")}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
