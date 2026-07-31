import { useMemo, useState, type CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { Check, Plus, X } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface Props {
  value: string[];
  onChange: (next: string[]) => void;
  suggestions: string[];
  placeholder?: string;
}

const captionFont: CSSProperties = { fontSize: "var(--font-caption)" };

export default function TagPicker({ value, onChange, suggestions, placeholder }: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const placeholderText = placeholder ?? t("strategies.tagsAdd");

  const trimmed = query.trim();
  const allCandidates = useMemo(() => {
    const set = new Set<string>([...suggestions, ...value]);
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [suggestions, value]);

  const filtered = useMemo(
    () =>
      trimmed === ""
        ? allCandidates
        : allCandidates.filter((c) =>
            c.toLowerCase().includes(trimmed.toLowerCase()),
          ),
    [allCandidates, trimmed],
  );

  const showCreateOption =
    trimmed.length > 0 &&
    !allCandidates.some((c) => c.toLowerCase() === trimmed.toLowerCase());

  const toggleTag = (tag: string) => {
    if (value.includes(tag)) onChange(value.filter((t) => t !== tag));
    else onChange([...value, tag]);
  };

  const removeTag = (tag: string) => onChange(value.filter((t) => t !== tag));

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div
          role="combobox"
          aria-expanded={open}
          tabIndex={0}
          className="flex min-h-8 w-full max-w-xs cursor-text flex-wrap items-center gap-1 rounded-[10px] border border-input bg-[var(--input-bg)] px-2 py-1 text-foreground transition-colors hover:border-primary/40 focus-visible:border-[var(--accent-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {value.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-caption text-foreground"
            >
              {tag}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  removeTag(tag);
                }}
                className="rounded text-muted-foreground hover:text-foreground"
                aria-label={t("strategies.tagsRemoveLabel", { tag })}
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
          {value.length === 0 && (
            <span className="px-1 text-caption text-muted-foreground">
              {placeholderText}
            </span>
          )}
          <span className="ml-auto inline-flex items-center px-1 text-caption text-muted-foreground">
            <Plus className="size-3" />
          </span>
        </div>
      </PopoverTrigger>
      <PopoverContent className="w-[220px] p-2" align="start">
        <Input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("strategies.tagsSearchPlaceholder")}
          style={captionFont}
          className="mb-2 h-7 px-2"
        />
        <div className="flex max-h-48 flex-col gap-0.5 overflow-y-auto">
          {filtered.map((tag) => {
            const selected = value.includes(tag);
            return (
              <button
                key={tag}
                type="button"
                onClick={() => toggleTag(tag)}
                style={captionFont}
                className="flex items-center gap-2 rounded px-2 py-1 text-left text-foreground hover:bg-muted"
              >
                <Check
                  className={cn(
                    "size-3 shrink-0",
                    selected ? "opacity-100" : "opacity-0",
                  )}
                />
                <span className="truncate">{tag}</span>
              </button>
            );
          })}
          {showCreateOption && (
            <button
              type="button"
              onClick={() => {
                onChange([...value, trimmed]);
                setQuery("");
              }}
              style={captionFont}
              className="flex items-center gap-2 rounded px-2 py-1 text-left text-foreground hover:bg-muted"
            >
              <Plus className="size-3 shrink-0" />
              <span className="truncate">
                {t("strategies.tagsCreate")} "{trimmed}"
              </span>
            </button>
          )}
          {filtered.length === 0 && !showCreateOption && (
            <div
              style={captionFont}
              className="px-2 py-1 text-muted-foreground"
            >
              {t("strategies.tagsEmpty")}
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
