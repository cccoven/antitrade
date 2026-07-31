import type { MouseEvent as ReactMouseEvent } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";

const INTERACTIVE_CHROME_TARGET_SELECTOR = [
  "a",
  "button",
  "input",
  "textarea",
  "select",
  "summary",
  "[role='button']",
  "[role='checkbox']",
  "[role='combobox']",
  "[role='link']",
  "[role='menuitem']",
  "[role='option']",
  "[role='radio']",
  "[role='slider']",
  "[role='switch']",
  "[contenteditable='true']",
  "[data-window-drag-exclude]",
].join(",");

export function isTauriShell() {
  return "__TAURI_INTERNALS__" in window;
}

function isWindowChromeDragTarget(target: EventTarget | null) {
  return (
    target instanceof Element &&
    !target.closest(INTERACTIVE_CHROME_TARGET_SELECTOR)
  );
}

export function handleWindowDragMouseDown(event: ReactMouseEvent<HTMLElement>) {
  if (
    !isTauriShell() ||
    event.button !== 0 ||
    event.detail > 1 ||
    !isWindowChromeDragTarget(event.target)
  ) {
    return;
  }

  event.preventDefault();
  void getCurrentWindow().startDragging().catch(() => undefined);
}

export function handleWindowDragDoubleClick(event: ReactMouseEvent<HTMLElement>) {
  if (
    !isTauriShell() ||
    event.button !== 0 ||
    !isWindowChromeDragTarget(event.target)
  ) {
    return;
  }

  event.preventDefault();
  void getCurrentWindow().toggleMaximize().catch(() => undefined);
}
