export type CalcSession = {
  datasetId: string | null;
  language: "relalg" | "sql";
  queryRelAlg: string;
  querySql: string;
};

export type HistoryEntry = {
  id: string;
  datasetId: string;
  datasetName?: string;
  language: "relalg" | "sql";
  query: string;
  at: number;
};

type LegacyCalcSession = {
  datasetId?: string | null;
  language?: "relalg" | "sql";
  query?: string;
  queryRelAlg?: string;
  querySql?: string;
};

const SESSION_KEY = "relax.calcSession";
const HISTORY_KEY = "relax.queryHistory";
const HISTORY_MAX = 40;

function normalizeSession(parsed: LegacyCalcSession): CalcSession | null {
  const language = parsed.language === "sql" ? "sql" : "relalg";
  if (
    typeof parsed.queryRelAlg === "string" &&
    typeof parsed.querySql === "string"
  ) {
    return {
      datasetId: parsed.datasetId ?? null,
      language,
      queryRelAlg: parsed.queryRelAlg,
      querySql: parsed.querySql,
    };
  }
  // Migrate older sessions that stored a single active query.
  if (typeof parsed.query === "string") {
    return {
      datasetId: parsed.datasetId ?? null,
      language,
      queryRelAlg: language === "relalg" ? parsed.query : "",
      querySql: language === "sql" ? parsed.query : "",
    };
  }
  return null;
}

export function loadSession(): CalcSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return normalizeSession(JSON.parse(raw) as LegacyCalcSession);
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
