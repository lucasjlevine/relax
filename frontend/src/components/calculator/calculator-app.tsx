"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlignLeft, PanelLeft, Play } from "lucide-react";
import {
  formatQuery,
  getDataset,
  listDatasets,
  runQuery,
  type DatasetDetail,
  type DatasetSummary,
  type QueryLanguage,
  type QueryResponse,
} from "@/lib/api";
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
import { ResultTable } from "@/components/calculator/result-table";
import { OperatorTreeView } from "@/components/calculator/operator-tree";

const SIDEBAR_MIN = 240;
const SIDEBAR_MAX = 640;
const SIDEBAR_DEFAULT = 300;
const SIDEBAR_MANAGE = 440;
const SIDEBAR_STORAGE_KEY = "relax.sidebarWidth";

function clampSidebar(width: number) {
  if (typeof window === "undefined") {
    return Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, width));
  }
  const max = Math.min(SIDEBAR_MAX, Math.floor(window.innerWidth * 0.55));
  return Math.min(max, Math.max(SIDEBAR_MIN, width));
}

export function CalculatorApp() {
  const editorRef = useRef<QueryEditorHandle>(null);
  const languageRef = useRef<QueryLanguage>("relalg");
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [language, setLanguage] = useState<QueryLanguage>("relalg");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [panelTab, setPanelTab] = useState<SchemaPanelTab>("schema");

  languageRef.current = language;

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
    async (id: string) => {
      const detail = await getDataset(id);
      setDataset(detail);
      setResult(null);
      setError(null);
      applyExample(detail, languageRef.current);
    },
    [applyExample],
  );

  const refreshDatasets = useCallback(
    async (selectId?: string) => {
      const list = await listDatasets();
      setDatasets(list);
      const id = selectId ?? list[0]?.id;
      if (id) {
        await loadDataset(id);
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
          setError(err instanceof Error ? err.message : "Failed to load datasets");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshDatasets]);

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
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  };

  const autoformat = async () => {
    setLoading(true);
    setError(null);
    try {
      const formatted = await formatQuery({ language, query });
      setQuery(formatted);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Format failed");
    } finally {
      setLoading(false);
    }
  };

  const syncDatasetList = (detail: DatasetDetail) => {
    setDatasets((prev) => {
      const exists = prev.some((d) => d.id === detail.id);
      if (!exists) {
        return [
          ...prev,
          { id: detail.id, name: detail.name, description: detail.description },
        ];
      }
      return prev.map((d) =>
        d.id === detail.id
          ? { id: detail.id, name: detail.name, description: detail.description }
          : d,
      );
    });
    setDataset(detail);
  };

  const onPanelChange = (tab: SchemaPanelTab) => {
    setPanelTab(tab);
    if (tab === "manage") {
      setSidebarCollapsed(false);
      setSidebarWidth((w) => clampSidebar(Math.max(w, SIDEBAR_MANAGE)));
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
          <Link href="/" className="font-serif text-xl tracking-tight text-primary">
            relax
          </Link>
          <Separator orientation="vertical" className="hidden h-5 sm:block" />
          <span className="hidden text-sm text-muted-foreground sm:inline">Calculator</span>
        </div>
        <div className="flex items-center gap-3">
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
          <Link
            href="/#guide"
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
                const first = detail.relations[0]?.name;
                if (first) {
                  setLanguage("relalg");
                  setQuery(`π_{*}(${first})`);
                }
              }}
              onDatasetUpdated={(detail) => {
                syncDatasetList(detail);
              }}
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
          <div className="shrink-0 space-y-3 border-b p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Tabs value={language} onValueChange={onLanguageChange}>
                <TabsList>
                  <TabsTrigger value="relalg">RelAlg</TabsTrigger>
                  <TabsTrigger value="sql">SQL</TabsTrigger>
                </TabsList>
              </Tabs>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  onClick={() => void autoformat()}
                  disabled={loading || !query.trim()}
                >
                  <AlignLeft className="h-4 w-4" aria-hidden />
                  Format
                </Button>
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
              onChange={setQuery}
              onExecute={() => void execute()}
            />
            <p className="text-xs text-muted-foreground">
              Type <code>π_&#123;…&#125;(R)</code> or prefix style — Format rewrites to classical
              subscripts. Drag the left edge to widen Manage. Shortcut: Ctrl/Cmd + Enter.
            </p>

            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
          </div>

          <div className="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)_minmax(140px,0.35fr)] md:grid-cols-[minmax(0,1fr)_220px] md:grid-rows-1">
            <section className="flex min-h-0 min-w-0 flex-col border-b md:border-b-0 md:border-r">
              <div className="shrink-0 border-b px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Results
              </div>
              <div className="min-h-0 flex-1 overflow-hidden">
                <ResultTable result={result} />
              </div>
            </section>
            <section className="flex min-h-0 min-w-0 flex-col overflow-hidden">
              <div className="shrink-0 border-b px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Operator tree
              </div>
              <div className="min-h-0 flex-1 overflow-hidden">
                <OperatorTreeView tree={result?.tree ?? null} />
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
