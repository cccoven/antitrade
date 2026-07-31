const SIDEBAR_COLLAPSED_KEY = "antitrade.sidebarCollapsed";

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function safeReadJson<T>(key: string): T | null {
  if (!canUseStorage()) return null;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeJson<T>(key: string, value: T) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

export function readSidebarCollapsed(defaultValue = false) {
  if (!canUseStorage()) return defaultValue;
  const raw = window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
  if (raw === "true") return true;
  if (raw === "false") return false;
  return defaultValue;
}

export function writeSidebarCollapsed(value: boolean) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(value));
}

// ─── Journal State ─────────────────────────────────────────

interface JournalState {
  filterSymbol: string;
  filterDirection: string; // "" | "long" | "short"
  filterPositionStatus: string; // "" | "open" | "closed"
  filterDateFrom: string;
  filterDateTo: string;
}

const JOURNAL_STATE_KEY = "antitrade.journalState";
const JOURNAL_AMOUNTS_VISIBLE_KEY = "antitrade.journalAmountsVisible";

export function readJournalState(defaultValue: JournalState): JournalState {
  const parsed = safeReadJson<Partial<JournalState>>(JOURNAL_STATE_KEY);
  if (!parsed) return defaultValue;

  return {
    filterSymbol: typeof parsed.filterSymbol === "string" ? parsed.filterSymbol : defaultValue.filterSymbol,
    filterDirection: typeof parsed.filterDirection === "string" ? parsed.filterDirection : defaultValue.filterDirection,
    filterPositionStatus: typeof parsed.filterPositionStatus === "string"
      ? parsed.filterPositionStatus
      : defaultValue.filterPositionStatus,
    filterDateFrom: typeof parsed.filterDateFrom === "string" ? parsed.filterDateFrom : defaultValue.filterDateFrom,
    filterDateTo: typeof parsed.filterDateTo === "string" ? parsed.filterDateTo : defaultValue.filterDateTo,
  };
}

export function writeJournalState(value: JournalState) {
  writeJson(JOURNAL_STATE_KEY, value);
}

export function readJournalAmountsVisible(defaultValue = true): boolean {
  if (!canUseStorage()) return defaultValue;
  const raw = window.localStorage.getItem(JOURNAL_AMOUNTS_VISIBLE_KEY);
  if (raw === "true") return true;
  if (raw === "false") return false;
  return defaultValue;
}

export function writeJournalAmountsVisible(value: boolean) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(JOURNAL_AMOUNTS_VISIBLE_KEY, String(value));
}

// ─── Portfolio State ───────────────────────────────────────

const PORTFOLIO_ACTIVE_ID_KEY = "antitrade.portfolio.activeId";

export function readActivePortfolioId(): string | null {
  if (!canUseStorage()) return null;
  return window.localStorage.getItem(PORTFOLIO_ACTIVE_ID_KEY);
}

export function writeActivePortfolioId(id: string | null) {
  if (!canUseStorage()) return;
  if (id === null) {
    window.localStorage.removeItem(PORTFOLIO_ACTIVE_ID_KEY);
  } else {
    window.localStorage.setItem(PORTFOLIO_ACTIVE_ID_KEY, id);
  }
}
