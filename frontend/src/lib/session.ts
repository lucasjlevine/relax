export type CalcSession = {
  datasetId: string | null;
  language: "relalg" | "sql";
  query: string;
};

export type HistoryEntry = {
  id: string;
  datasetId: string;
  datasetName?: string;
  language: "relalg" | "sql";
  query: string;
  at: number;
};

const SESSION_KEY = "relax.calcSession";
const HISTORY_KEY = "relax.queryHistory";
const HISTORY_MAX = 40;

export function loadSession(): CalcSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CalcSession;
    if (typeof parsed.query !== "string") return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveSession(session: CalcSession): void {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    /* ignore */
  }
}

export function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as HistoryEntry[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function pushHistory(entry: Omit<HistoryEntry, "id" | "at">): HistoryEntry[] {
  const next: HistoryEntry = {
    ...entry,
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    at: Date.now(),
  };
  const prev = loadHistory();
  const deduped = prev.filter(
    (h) => !(h.datasetId === next.datasetId && h.language === next.language && h.query === next.query),
  );
  const list = [next, ...deduped].slice(0, HISTORY_MAX);
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
  } catch {
    /* ignore */
  }
  return list;
}
