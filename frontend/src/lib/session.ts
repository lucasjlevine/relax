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

export type WorkspaceState = {
  queryRelAlg: string;
  querySql: string;
  language: "relalg" | "sql";
  history: HistoryEntry[];
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
const WORKSPACES_KEY = "relax.workspaces";
const ACTIVE_KEY = "relax.activeWorkspaceId";
/** Set after a successful one-time import from legacy session/history keys. */
const MIGRATED_KEY = "relax.workspacesMigrated";
const HISTORY_MAX = 40;

function emptyWorkspace(
  language: "relalg" | "sql" = "relalg",
): WorkspaceState {
  return {
    queryRelAlg: "",
    querySql: "",
    language,
    history: [],
  };
}

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

function loadWorkspacesRaw(): Record<string, WorkspaceState> {
  try {
    const raw = localStorage.getItem(WORKSPACES_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, WorkspaceState>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveWorkspacesRaw(map: Record<string, WorkspaceState>): void {
  try {
    localStorage.setItem(WORKSPACES_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

/**
 * One-time migration from legacy global session/history into per-dataset workspaces.
 *
 * Never deletes `relax.calcSession` or `relax.queryHistory` — students keep a
 * fallback copy even after workspaces are populated.
 */
function migrateLegacyIfNeeded(): void {
  try {
    if (localStorage.getItem(MIGRATED_KEY) === "1") return;

    const existing = loadWorkspacesRaw();
    const hasWorkspaceData = Object.keys(existing).some((id) => {
      const w = existing[id];
      return Boolean(
        w &&
          (w.queryRelAlg?.trim() ||
            w.querySql?.trim() ||
            (Array.isArray(w.history) && w.history.length > 0)),
      );
    });
    // Already using workspaces with real content — just mark migrated.
    if (hasWorkspaceData) {
      localStorage.setItem(MIGRATED_KEY, "1");
      return;
    }

    const map: Record<string, WorkspaceState> = { ...existing };
    const session = loadSession();
    const history = loadHistory();

    if (session?.datasetId) {
      const prev = map[session.datasetId] ?? emptyWorkspace(session.language);
      map[session.datasetId] = {
        queryRelAlg: session.queryRelAlg || prev.queryRelAlg,
        querySql: session.querySql || prev.querySql,
        language: session.language,
        history:
          prev.history.length > 0
            ? prev.history
            : history
                .filter((h) => h.datasetId === session.datasetId)
                .slice(0, HISTORY_MAX),
      };
      if (!localStorage.getItem(ACTIVE_KEY)) {
        localStorage.setItem(ACTIVE_KEY, session.datasetId);
      }
    }

    for (const h of history) {
      if (!h?.datasetId) continue;
      if (!map[h.datasetId]) {
        map[h.datasetId] = emptyWorkspace(h.language);
      }
      if (!map[h.datasetId].history.some((x) => x.id === h.id)) {
        map[h.datasetId].history.push(h);
      }
    }
    for (const id of Object.keys(map)) {
      map[id].history = map[id].history
        .slice()
        .sort((a, b) => b.at - a.at)
        .slice(0, HISTORY_MAX);
    }
    saveWorkspacesRaw(map);
    localStorage.setItem(MIGRATED_KEY, "1");
  } catch {
    /* ignore — leave legacy keys intact */
  }
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
  if (session.datasetId) {
    const ws = getWorkspace(session.datasetId);
    saveWorkspace(session.datasetId, {
      ...ws,
      queryRelAlg: session.queryRelAlg,
      querySql: session.querySql,
      language: session.language,
    });
    setActiveWorkspaceId(session.datasetId);
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

/** @deprecated Prefer pushWorkspaceHistory — kept for migration / tests. */
export function pushHistory(entry: Omit<HistoryEntry, "id" | "at">): HistoryEntry[] {
  return pushWorkspaceHistory(entry.datasetId, entry);
}

export function getActiveWorkspaceId(): string | null {
  migrateLegacyIfNeeded();
  try {
    return localStorage.getItem(ACTIVE_KEY);
  } catch {
    return null;
  }
}

export function setActiveWorkspaceId(id: string | null): void {
  try {
    if (id) localStorage.setItem(ACTIVE_KEY, id);
    else localStorage.removeItem(ACTIVE_KEY);
  } catch {
    /* ignore */
  }
}

export function getWorkspace(datasetId: string): WorkspaceState {
  migrateLegacyIfNeeded();
  const map = loadWorkspacesRaw();
  return map[datasetId] ? { ...emptyWorkspace(), ...map[datasetId] } : emptyWorkspace();
}

export function saveWorkspace(datasetId: string, state: WorkspaceState): void {
  migrateLegacyIfNeeded();
  const map = loadWorkspacesRaw();
  map[datasetId] = {
    queryRelAlg: state.queryRelAlg,
    querySql: state.querySql,
    language: state.language === "sql" ? "sql" : "relalg",
    history: Array.isArray(state.history)
      ? state.history.slice(0, HISTORY_MAX)
      : [],
  };
  saveWorkspacesRaw(map);
}

export function loadWorkspaceHistory(datasetId: string): HistoryEntry[] {
  return getWorkspace(datasetId).history;
}

export function pushWorkspaceHistory(
  datasetId: string,
  entry: Omit<HistoryEntry, "id" | "at">,
): HistoryEntry[] {
  const next: HistoryEntry = {
    ...entry,
    datasetId,
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    at: Date.now(),
  };
  const ws = getWorkspace(datasetId);
  const deduped = ws.history.filter(
    (h) =>
      !(
        h.datasetId === next.datasetId &&
        h.language === next.language &&
        h.query === next.query
      ),
  );
  const history = [next, ...deduped].slice(0, HISTORY_MAX);
  saveWorkspace(datasetId, { ...ws, history });
  // Keep legacy global history in sync for older readers.
  try {
    const prev = loadHistory().filter(
      (h) =>
        !(
          h.datasetId === next.datasetId &&
          h.language === next.language &&
          h.query === next.query
        ),
    );
    localStorage.setItem(
      HISTORY_KEY,
      JSON.stringify([next, ...prev].slice(0, HISTORY_MAX * 3)),
    );
  } catch {
    /* ignore */
  }
  return history;
}
