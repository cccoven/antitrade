import { isTauriShell } from "./window-chrome";

/**
 * Open an external URL from either the browser or the Tauri desktop shell.
 * In a browser, window.open works from a user gesture. In the Tauri webview
 * window.open is a no-op, so we route through the opener plugin (opens the
 * OS default browser).
 */
export async function openExternal(url: string): Promise<void> {
  if (!/^https?:\/\//.test(url)) return;
  if (isTauriShell()) {
    try {
      const { openUrl } = await import("@tauri-apps/plugin-opener");
      await openUrl(url);
      return;
    } catch {
      // fall through to window.open as a last resort
    }
  }
  window.open(url, "_blank", "noopener,noreferrer");
}
