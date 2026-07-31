import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { assistantControlSizes, assistantInputStyle } from "../assistant-ui-config";
import type { InterruptItem } from "./assistant-types";

interface Props {
  items: InterruptItem[];
  resolved?: "approved" | "rejected" | "expired";
  onApprove: () => void;
  onReject: () => void;
}

export function ActionConfirmCard({ items, resolved, onApprove, onReject }: Props) {
  const { t } = useTranslation();
  const isDestructive = items.some((item) => item.action === "delete");

  return (
    <div
      className={cn(
        "w-full max-w-[85%] rounded-lg border p-3",
        isDestructive ? "border-destructive/50" : "border-border",
      )}
    >
      {items.map((item) => (
        <div key={item.call_id} className="mb-2 last:mb-0">
          <div
            className={cn(
              "text-ui font-medium",
              item.action === "delete" && "text-destructive",
            )}
          >
            {item.title}
          </div>
          {item.preview.length > 0 && (
            <ul className="mt-1 space-y-0.5">
              {item.preview.map((line, index) => (
                <li key={`${item.call_id}-${index}`} className="text-caption text-muted-foreground">
                  {line.label}
                  {line.sub ? ` - ${line.sub}` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}

      {resolved ? (
        <div className="mt-2 text-caption text-muted-foreground">
          {t(`assistant.confirm.${resolved}`)}
        </div>
      ) : (
        <div className="mt-3 flex justify-end gap-2">
          <Button
            variant="outline"
            size={assistantControlSizes.primaryAction}
            style={assistantInputStyle}
            onClick={onReject}
          >
            {t("assistant.confirm.cancel")}
          </Button>
          <Button
            variant={isDestructive ? "destructive" : "default"}
            size={assistantControlSizes.primaryAction}
            style={assistantInputStyle}
            onClick={onApprove}
          >
            {t("assistant.confirm.confirm")}
          </Button>
        </div>
      )}
    </div>
  );
}
