import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Trash2, Tag, Download, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import BatchTagPopover from "@/components/BatchTagPopover";

interface BatchToolbarProps {
  selectedCount: number;
  totalMatching: number;
  selectedOnPage: number;
  currentPageLen: number;
  allMatching: boolean;
  existingTags?: string[];
  onSelectAllMatching: () => void;
  onClearSelection: () => void;
  onBatchDelete: () => void;
  onBatchTagConfirm: (tags: string[]) => void;
  onExportSelected: () => void;
}

const UI_STYLE = { fontSize: "var(--font-ui)", fontWeight: 400 };

export default function BatchToolbar({
  selectedCount,
  totalMatching,
  selectedOnPage,
  currentPageLen,
  allMatching,
  existingTags,
  onSelectAllMatching,
  onClearSelection,
  onBatchDelete,
  onBatchTagConfirm,
  onExportSelected,
}: BatchToolbarProps) {
  const { t } = useTranslation();
  const [tagOpen, setTagOpen] = useState(false);

  const showCrossPageCta =
    !allMatching &&
    currentPageLen > 0 &&
    selectedOnPage === currentPageLen &&
    totalMatching > currentPageLen;

  return (
    <div
      className="sticky top-0 z-10 flex flex-wrap items-center gap-2 rounded-md border border-border bg-[var(--chip-bg)] px-3 py-2"
      style={UI_STYLE}
    >
      <span className="text-foreground">
        {allMatching
          ? t("journal.batch.selectedCount", { count: totalMatching })
          : t("journal.batch.selectedOfTotal", {
              count: selectedCount,
              total: totalMatching,
            })}
      </span>

      {allMatching && (
        <span className="rounded bg-primary/15 px-2 py-0.5 text-caption text-primary">
          {t("journal.batch.crossPage")}
        </span>
      )}

      {showCrossPageCta && (
        <Button
          variant="link"
          size="sm"
          style={UI_STYLE}
          onClick={onSelectAllMatching}
        >
          {t("journal.batch.selectAllMatching", { count: totalMatching })}
        </Button>
      )}

      <div className="ml-auto flex items-center gap-2">
        <BatchTagPopover
          open={tagOpen}
          onOpenChange={setTagOpen}
          existingTags={existingTags}
          onConfirm={(tags) => {
            setTagOpen(false);
            onBatchTagConfirm(tags);
          }}
          triggerTooltip={t("journal.batch.tag")}
          trigger={
            <Button
              variant="outline"
              size="icon-sm"
              style={UI_STYLE}
              aria-label={t("journal.batch.tag")}
            >
              <Tag />
            </Button>
          }
        />
        <TooltipIconButton
          label={t("journal.batch.export")}
          variant="outline"
          size="icon-sm"
          style={UI_STYLE}
          onClick={onExportSelected}
        >
          <Download />
        </TooltipIconButton>
        <TooltipIconButton
          label={t("journal.batch.delete")}
          variant="outline"
          size="icon-sm"
          style={UI_STYLE}
          onClick={onBatchDelete}
          className="hover:border-destructive hover:bg-destructive/10 hover:text-destructive"
        >
          <Trash2 />
        </TooltipIconButton>
        <TooltipIconButton
          label={t("journal.batch.cancel")}
          variant="ghost"
          size="icon-sm"
          onClick={onClearSelection}
        >
          <X />
        </TooltipIconButton>
      </div>
    </div>
  );
}
