import type { ComponentProps } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type TooltipIconButtonProps = ComponentProps<typeof Button> & {
  label: string;
  tooltipSide?: ComponentProps<typeof TooltipContent>["side"];
};

function TooltipIconButton({
  label,
  tooltipSide = "bottom",
  "aria-label": ariaLabel,
  children,
  ...props
}: TooltipIconButtonProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button aria-label={ariaLabel ?? label} {...props}>
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent side={tooltipSide}>{label}</TooltipContent>
    </Tooltip>
  );
}

export { TooltipIconButton };
