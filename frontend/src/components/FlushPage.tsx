import { cn } from "@/lib/utils";
import ControlStrip from "./ControlStrip";

interface FlushPageProps {
  /** Primary toolbar actions, rendered in the strip's main slot. */
  toolbar: React.ReactNode;
  /** Secondary toolbar actions, rendered in the strip's aside slot. */
  toolbarAside?: React.ReactNode;
  /** Inner content. */
  children: React.ReactNode;
  /** Extra classes for the content wrapper (overrides defaults). */
  contentClassName?: string;
}

/**
 * Standard page shell for routes with a sticky flush-top toolbar
 * (Journal, Strategies, Daily Review, Portfolio, Backtest, etc.).
 *
 * Encapsulates:
 *   - The page-stack-journal + journal-content layout classes.
 *   - The ControlStrip with control-strip-flush styling.
 *
 * The shell auto-detects the flush strip via `:has(.control-strip-flush)`
 * in index.css to remove the default 8px shell top padding, so this
 * component does not need to know which route it's on.
 *
 * Default content layout: `flex flex-col gap-4 pt-4`. Pass
 * contentClassName to override (e.g., `pt-0` for pages whose first
 * card already provides spacing, or `pt-3` for tighter pages).
 */
export default function FlushPage({
  toolbar,
  toolbarAside,
  children,
  contentClassName,
}: FlushPageProps) {
  return (
    <div className="page-stack page-stack-journal">
      <ControlStrip className="control-strip-flush" aside={toolbarAside}>
        {toolbar}
      </ControlStrip>
      <div className={cn("journal-content flex flex-col gap-4 pt-4", contentClassName)}>
        {children}
      </div>
    </div>
  );
}
