import {
  handleWindowDragDoubleClick,
  handleWindowDragMouseDown,
} from "@/lib/window-chrome";

interface ControlStripProps {
  children: React.ReactNode;
  aside?: React.ReactNode;
  className?: string;
}

export default function ControlStrip({
  children,
  aside,
  className = "",
}: ControlStripProps) {
  return (
    <div
      className={`control-strip ${className}`.trim()}
      data-window-drag-region
      onMouseDown={handleWindowDragMouseDown}
      onDoubleClick={handleWindowDragDoubleClick}
    >
      <div className="control-strip-main">{children}</div>
      {aside ? <div className="control-strip-aside">{aside}</div> : null}
    </div>
  );
}
