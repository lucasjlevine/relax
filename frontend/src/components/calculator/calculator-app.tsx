"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { AlignLeft, History, PanelLeft, Play } from "lucide-react";
import {
  formatQuery,
  getDataset,
  getSharedDataset,
  copySharedDataset,
  listDatasets,
  runQuery,
  errorTitle,
  type DatasetDetail,
  type DatasetSummary,
  type QueryLanguage,
  type QueryResponse,
} from "@/lib/api";
import {
  loadHistory,
  loadSession,
  pushHistory,
  saveSession,
  type HistoryEntry,
} from "@/lib/session";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { SchemaPanel, type SchemaPanelTab } from "@/components/calculator/schema-panel";
import {
  QueryEditor,
  type QueryEditorHandle,
} from "@/components/calculator/query-editor";
import { OperatorToolbar } from "@/components/calculator/operator-toolbar";
import { FunctionsPanel } from "@/components/calculator/functions-panel";
import { ResultsWorkspace } from "@/components/calculator/results-workspace";

const SIDEBAR_MIN = 240;
const SIDEBAR_MAX = 720;
const SIDEBAR_DEFAULT = 300;
const SIDEBAR_MANAGE = 440;
const SIDEBAR_GROUP = 520;
const SIDEBAR_STORAGE_KEY = "relax.sidebarWidth";

function clampSidebar(width: number) {
  if (typeof window === "undefined") {
    return Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, width));
  }
  const max = Math.min(SIDEBAR_MAX, Math.floor(window.innerWidth * 0.55));
  return Math.min(max, Math.max(SIDEBAR_MIN, width));
}

function HistoryDropdown({
  history,
  anchorRef,
  onClose,
  onPick,
}: {
  history: HistoryEntry[];
  anchorRef: React.RefObject<HTMLElement | null>;
  onClose: () => void;
  onPick: (h: HistoryEntry) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const onClick = (e: MouseEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t)) return;
      if (anchorRef.current?.contains(t)) return;
      onClose();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [onClose, anchorRef]);

  if (typeof document === "undefined") return null;

  const rect = anchorRef.current?.getBoundingClientRect();
  const top = rect ? rect.bottom + 6 : 120;
  const right = rect ? Math.max(8, window.innerWidth - rect.right) : 16;

  return createPortal(
    <div
      ref={ref}
      style={{ top, right }}
      className="fixed z-[100] max-h-64 w-[min(24rem,90vw)] overflow-auto rounded-md border bg-card p-1 shadow-xl"
      role="listbox"
      aria-label="Query history"
    >
      {history.map((h) => (
        <button
          key={h.id}
          type="button"
          className="block w-full rounded px-2 py-1.5 text-left text-xs hover:bg-muted"
          onClick={() => onPick(h)}
        >
          <span className="font-medium text-foreground">
            {h.datasetName ?? h.datasetId}
          </span>
          <span className="ml-2 uppercase text-muted-foreground">{h.language}</span>
          <div className="mt-0.5 truncate font-mono text-muted-foreground">
            {h.query}
          </div>
        </button>
      ))}
    </div>,
    document.body,
  );
}

function FormatDropdown({
  anchorRef,
  onClose,
  onPick,
}: {
  anchorRef: React.RefObject<HTMLElement | null>;
  onClose: () => void;
  onPick: (style: "pretty" | "dense") => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const onClick = (e: MouseEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t)) return;
      if (anchorRef.current?.contains(t)) return;
      onClose();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [onClose, anchorRef]);

  if (typeof document === "undefined") return null;

  const rect = anchorRef.current?.getBoundingClientRect();
  const top = rect ? rect.bottom + 6 : 120;
  const right = rect ? Math.max(8, window.innerWidth - rect.right) : 16;

  return createPortal(
    <div
      ref={ref}
      style={{ top, right }}
      className="fixed z-[100] w-[12rem] rounded-md border bg-card p-1 shadow-xl"
      role="menu"
      aria-label="Format style"
    >
      <button
        type="button"
        role="menuitem"
        className="block w-full rounded px-2 py-1.5 text-left text-xs hover:bg-muted"
        onClick={() => onPick("pretty")}
      >
        <span className="font-medium text-foreground">Pretty</span>
        <div className="text-muted-foreground">Indented, fully parenthesized</div>
      </button>
      <button
        type="button"
        role="menuitem"
        className="block w-full rounded px-2 py-1.5 text-left text-xs hover:bg-muted"
        onClick={() => onPick("dense")}
      >
        <span className="font-medium text-foreground">Dense</span>
        <div className="text-muted-foreground">Compact, fewer parentheses</div>
      </button>
    </div>,
    document.body,
  );
}

export function CalculatorApp() {
  const editorRef = useRef<QueryEditorHandle>(null);
  const languageRef = useRef<QueryLanguage>("relalg");
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const skipNextExample = useRef(false);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [language, setLanguage] = useState<QueryLanguage>("relalg");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorHeading, setErrorHeading] = useState("Couldn’t run query");
  const [loading, setLoading] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [panelTab, setPanelTab] = useState<SchemaPanelTab>("schema");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [formatOpen, setFormatOpen] = useState(false);
  const [functionsOpen, setFunctionsOpen] = useState(false);
  const [forkNotice, setForkNotice] = useState<string | null>(null);
  const [sharePrompt, setSharePrompt] = useState<{
    token: string;
    detail: DatasetDetail;
  } | null>(null);
  const functionsBtnRef = useRef<HTMLButtonElement>(null);
  const historyBtnRef = useRef<HTMLButtonElement>(null);
  const formatBtnRef = useRef<HTMLButtonElement>(null);
  const booted = useRef(false);

  languageRef.current = language;

  useEffect(() => {
    setHistory(loadHistory());
  }, []);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");
    const sync = () => {
      if (mq.matches) setSidebarCollapsed(true);
    };
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(SIDEBAR_STORAGE_KEY);
      if (raw) setSidebarWidth(clampSidebar(Number(raw)));
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, String(sidebarWidth));
    } catch {
      /* ignore */
    }
  }, [sidebarWidth]);

  useEffect(() => {
    if (!booted.current) return;
    saveSession({
      datasetId: dataset?.id ?? null,
      language,
      query,
    });
  }, [dataset?.id, language, query]);

  const applyExample = useCallback(
    (detail: DatasetDetail, lang: QueryLanguage) => {
      if (lang === "sql" && detail.exampleSql) {
        setQuery(detail.exampleSql.trim());
      } else if (detail.exampleRelAlg) {
        setQuery(detail.exampleRelAlg.trim());
      }
    },
    [],
  );

  const loadDataset = useCallback(
    async (id: string, opts?: { keepQuery?: boolean }) => {
      const detail = await getDataset(id);
      setDataset(detail);
      setResult(null);
      setError(null);
      if (opts?.keepQuery || skipNextExample.current) {
        skipNextExample.current = false;
        return;
      }
      applyExample(detail, languageRef.current);
    },
    [applyExample],
  );

  const refreshDatasets = useCallback(
    async (selectId?: string) => {
      const list = await listDatasets();
      setDatasets(list);
      const session = !booted.current ? loadSession() : null;
      const id =
        selectId ??
        (session?.datasetId && list.some((d) => d.id === session.datasetId)
          ? session.datasetId
          : list[0]?.id);
      if (!booted.current && session) {
        if (session.language === "relalg" || session.language === "sql") {
          setLanguage(session.language);
          languageRef.current = session.language;
        }
        if (session.query.trim()) {
          setQuery(session.query);
          skipNextExample.current = true;
        }
      }
      booted.current = true;
      if (id) {
        await loadDataset(id, { keepQuery: skipNextExample.current });
      } else {
        setDataset(null);
        setQuery("");
        setResult(null);
      }
    },
    [loadDataset],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await refreshDatasets();
      } catch (err) {
        if (!cancelled) {
          setErrorHeading(errorTitle(err, "Couldn’t load datasets"));
          setError(err instanceof Error ? err.message : "Failed to load datasets");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshDatasets]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const token = new URLSearchParams(window.location.search).get("share");
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const detail = await getSharedDataset(token);
        if (cancelled) return;
        setSharePrompt({ token, detail });
      } catch (err) {
        if (!cancelled) {
          setErrorHeading(errorTitle(err, "Couldn’t open share link"));
          setError(err instanceof Error ? err.message : "Invalid share link");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onLanguageChange = (value: string) => {
    const next = value as QueryLanguage;
    setLanguage(next);
    if (!dataset) return;
    applyExample(dataset, next);
  };

  const execute = async () => {
    if (!dataset) return;
    setLoading(true);
    setError(null);
    try {
      const res = await runQuery({
        datasetId: dataset.id,
        language,
        query,
      });
      setResult(res);
      if (res.datasetId && res.datasetId !== dataset.id) {
        const detail = await getDataset(res.datasetId);
        syncDatasetList(detail, { previousId: dataset.id });
        if (detail.forkedFrom) {
          setForkNotice(
            `Saved as a personal copy of “${detail.forkedFrom}”. Column types were updated for this query.`,
          );
        }
      } else if (res.typeChanges && res.typeChanges.length > 0) {
        const detail = await getDataset(dataset.id);
        syncDatasetList(detail);
      }
      setHistory(
        pushHistory({
          datasetId: res.datasetId ?? dataset.id,
          datasetName: dataset.name,
          language,
          query: query.trim(),
        }),
      );
    } catch (err) {
      setResult(null);
      setErrorHeading(errorTitle(err));
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  };

  const autoformat = async (style: "pretty" | "dense" = "pretty") => {
    setLoading(true);
    setError(null);
    try {
      const formatted = await formatQuery({ language, query, style });
      setQuery(formatted);
      setFormatOpen(false);
    } catch (err) {
      setErrorHeading(errorTitle(err, "Couldn’t format query"));
      setError(err instanceof Error ? err.message : "Format failed");
    } finally {
      setLoading(false);
    }
  };

  const syncDatasetList = (detail: DatasetDetail, opts?: { previousId?: string }) => {
    const previousId = opts?.previousId;
    setDatasets((prev) => {
      let next = prev;
      if (previousId && previousId !== detail.id) {
        // Keep built-in in list; add forked copy
        next = prev.filter((d) => d.id !== detail.id);
      }
      const exists = next.some((d) => d.id === detail.id);
      const summary = {
        id: detail.id,
        name: detail.name,
        description: detail.description,
        owned: detail.owned,
        isBuiltin: detail.isBuiltin,
      };
      if (!exists) {
        return [...next, summary];
      }
      return next.map((d) => (d.id === detail.id ? summary : d));
    });
    setDataset(detail);
    if (previousId && previousId !== detail.id && detail.forkedFrom) {
      setForkNotice(
        `Saved as a personal copy of “${detail.forkedFrom}”. Further edits stay on this copy.`,
      );
    }
  };

  const onDatasetUpdated = (detail: DatasetDetail) => {
    const previousId = dataset?.id;
    syncDatasetList(detail, { previousId });
  };
  const onPanelChange = (tab: SchemaPanelTab) => {
    setPanelTab(tab);
    if (tab === "manage" || tab === "group") {
      setSidebarCollapsed(false);
      const min = tab === "group" ? SIDEBAR_GROUP : SIDEBAR_MANAGE;
      setSidebarWidth((w) => clampSidebar(Math.max(w, min)));
    }
  };

  const onResizeStart = (event: React.MouseEvent) => {
    event.preventDefault();
    dragRef.current = { startX: event.clientX, startWidth: sidebarWidth };
    const onMove = (e: MouseEvent) => {
      if (!dragRef.current) return;
      const delta = e.clientX - dragRef.current.startX;
      setSidebarWidth(clampSidebar(dragRef.current.startWidth + delta));
    };
    const onUp = () => {
      dragRef.current = null;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  const effectiveWidth = sidebarCollapsed ? 0 : sidebarWidth;

  const schemaHint = dataset
    ? {
        relations: dataset.relations.map((r) => ({
          name: r.name,
          columns: r.columns.map((c) => ({ name: c.name, type: c.type })),
        })),
      }
    : null;

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-[radial-gradient(ellipse_at_top,_#e8f4f2_0%,_hsl(var(--background))_55%)]">
      <header className="flex shrink-0 items-center justify-between border-b bg-card/80 px-4 py-3 backdrop-blur">
        <div className="flex items-center gap-3">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="md:hidden"
            aria-label={sidebarCollapsed ? "Show datasets panel" : "Hide datasets panel"}
            onClick={() => setSidebarCollapsed((c) => !c)}
          >
            <PanelLeft className="h-4 w-4" />
          </Button>
          <Link
            href="/"
            className="font-serif text-base tracking-tight text-primary sm:text-lg"
          >
            Relational Playground
          </Link>
          <Separator orientation="vertical" className="hidden h-5 sm:block" />
          <span className="hidden text-sm text-muted-foreground sm:inline">Calculator</span>
        </div>
        <div className="relative z-40 flex items-center gap-3">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="hidden md:inline-flex"
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => setSidebarCollapsed((c) => !c)}
          >
            <PanelLeft className="h-4 w-4" />
            {sidebarCollapsed ? "Show panel" : "Hide panel"}
          </Button>
          <button
            ref={functionsBtnRef}
            type="button"
            className="text-sm text-muted-foreground hover:text-foreground"
            onClick={() => {
              setFunctionsOpen((o) => !o);
              setHistoryOpen(false);
            }}
          >
            Functions
          </button>
          <FunctionsPanel
            open={functionsOpen}
            onClose={() => setFunctionsOpen(false)}
            anchorRef={functionsBtnRef}
          />
          <Link
            href="/guide"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Guide
          </Link>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <div
          className={`relative flex min-h-0 shrink-0 overflow-hidden border-r bg-card/70 transition-[width] duration-200 ease-out ${
            sidebarCollapsed ? "border-r-0" : ""
          }`}
          style={{ width: effectiveWidth }}
        >
          <div
            className="flex h-full min-w-0 flex-1 flex-col"
            style={{ width: sidebarWidth, minWidth: sidebarWidth }}
          >
            <SchemaPanel
              dataset={dataset}
              datasets={datasets}
              activeTab={panelTab}
              onTabChange={onPanelChange}
              onSelectDataset={(id) => {
                void loadDataset(id);
              }}
              onDatasetCreated={(detail) => {
                syncDatasetList(detail);
                setResult(null);
                setError(null);
                setForkNotice(null);
                const first = detail.relations[0]?.name;
                if (first) {
                  setLanguage("relalg");
                  setQuery(`π_{*}(${first})`);
                }
              }}
              onDatasetUpdated={onDatasetUpdated}
              onDatasetDeleted={async (id) => {
                const remaining = datasets.filter((d) => d.id !== id);
                setDatasets(remaining);
                if (dataset?.id === id) {
                  if (remaining[0]) {
                    await loadDataset(remaining[0].id);
                  } else {
                    setDataset(null);
                    setQuery("");
                    setResult(null);
                  }
                }
              }}
              onGroupsInstalled={(groups) => {
                for (const g of groups) {
                  syncDatasetList(g);
                }
                const last = groups[groups.length - 1];
                if (!last) return;
                setResult(null);
                setError(null);
                setForkNotice(null);
                if (last.exampleRelAlg) {
                  setLanguage("relalg");
                  setQuery(last.exampleRelAlg.trim());
                } else if (last.exampleSql) {
                  setLanguage("sql");
                  setQuery(last.exampleSql.trim());
                } else {
                  const first = last.relations[0]?.name;
                  if (first) {
                    setLanguage("relalg");
                    setQuery(`π_{*}(${first})`);
                  }
                }
              }}
            />
          </div>
          {!sidebarCollapsed ? (
            <button
              type="button"
              aria-label="Resize sidebar"
              className="absolute inset-y-0 right-0 z-10 w-1.5 cursor-col-resize bg-transparent hover:bg-primary/20 active:bg-primary/30"
              onMouseDown={onResizeStart}
            />
          ) : null}
        </div>

        <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          {forkNotice ? (
            <div className="shrink-0 border-b bg-primary/5 px-4 py-2 text-sm text-foreground">
              {forkNotice}{" "}
              <button
                type="button"
                className="underline"
                onClick={() => setForkNotice(null)}
              >
                Dismiss
              </button>
            </div>
          ) : null}
          {sharePrompt ? (
            <div className="shrink-0 border-b bg-card px-4 py-3 text-sm">
              <p className="font-medium">
                Shared dataset: {sharePrompt.detail.name}
              </p>
              <p className="mt-1 text-muted-foreground">
                {sharePrompt.detail.description ||
                  `${sharePrompt.detail.relations.length} relation(s). Add a copy to your library to query and edit.`}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  onClick={async () => {
                    try {
                      const copied = await copySharedDataset(sharePrompt.token);
                      syncDatasetList(copied);
                      setSharePrompt(null);
                      setForkNotice(null);
                      const url = new URL(window.location.href);
                      url.searchParams.delete("share");
                      window.history.replaceState({}, "", url.pathname);
                      if (copied.exampleRelAlg) {
                        setLanguage("relalg");
                        setQuery(copied.exampleRelAlg.trim());
                      } else {
                        const first = copied.relations[0]?.name;
                        if (first) {
                          setLanguage("relalg");
                          setQuery(`π_{*}(${first})`);
                        }
                      }
                    } catch (err) {
                      setErrorHeading(errorTitle(err, "Couldn’t copy dataset"));
                      setError(
                        err instanceof Error ? err.message : "Copy failed",
                      );
                    }
                  }}
                >
                  Add to my datasets
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setSharePrompt(null);
                    const url = new URL(window.location.href);
                    url.searchParams.delete("share");
                    window.history.replaceState({}, "", url.pathname);
                  }}
                >
                  Dismiss
                </Button>
              </div>
            </div>
          ) : null}
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto border-b p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Tabs value={language} onValueChange={onLanguageChange}>
                <TabsList>
                  <TabsTrigger value="relalg">RelAlg</TabsTrigger>
                  <TabsTrigger value="sql">SQL</TabsTrigger>
                </TabsList>
              </Tabs>
              <div className="relative z-30 flex gap-2">
                <Button
                  ref={historyBtnRef}
                  type="button"
                  variant="outline"
                  disabled={!history.length}
                  onClick={() => {
                    setHistoryOpen((o) => !o);
                    setFunctionsOpen(false);
                  }}
                >
                  <History className="h-4 w-4" aria-hidden />
                  History
                </Button>
                {historyOpen ? (
                  <HistoryDropdown
                    history={history}
                    anchorRef={historyBtnRef}
                    onClose={() => setHistoryOpen(false)}
                    onPick={(h) => {
                      setLanguage(h.language);
                      languageRef.current = h.language;
                      setQuery(h.query);
                      setHistoryOpen(false);
                      if (h.datasetId !== dataset?.id) {
                        skipNextExample.current = true;
                        void loadDataset(h.datasetId, { keepQuery: true });
                      }
                    }}
                  />
                ) : null}
                <Button
                  ref={formatBtnRef}
                  variant="secondary"
                  onClick={() => {
                    setHistoryOpen(false);
                    setFunctionsOpen(false);
                    setFormatOpen((o) => !o);
                  }}
                  disabled={loading || !query.trim()}
                >
                  <AlignLeft className="h-4 w-4" aria-hidden />
                  Format
                </Button>
                {formatOpen ? (
                  <FormatDropdown
                    anchorRef={formatBtnRef}
                    onClose={() => setFormatOpen(false)}
                    onPick={(style) => void autoformat(style)}
                  />
                ) : null}
                <Button onClick={() => void execute()} disabled={loading || !dataset}>
                  <Play className="h-4 w-4" aria-hidden />
                  {loading ? "Working…" : "Execute"}
                </Button>
              </div>
            </div>

            {language === "relalg" ? (
              <OperatorToolbar
                onInsert={(text, cursorOffset) =>
                  editorRef.current?.insertAtCursor(text, cursorOffset)
                }
                disabled={loading}
              />
            ) : null}

            <QueryEditor
              ref={editorRef}
              value={query}
              language={language}
              schema={schemaHint}
              onChange={setQuery}
              onExecute={() => void execute()}
            />

            {error ? (
              <Alert variant="destructive">
                <AlertTitle>{errorHeading}</AlertTitle>
                <AlertDescription className="whitespace-pre-wrap font-mono text-[13px] leading-relaxed">
                  {error}
                </AlertDescription>
              </Alert>
            ) : null}
          </div>

          <ResultsWorkspace result={result} />
        </main>
      </div>
    </div>
  );
}
