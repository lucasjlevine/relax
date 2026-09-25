"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlignLeft, Play } from "lucide-react";
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
import { SchemaPanel } from "@/components/calculator/schema-panel";
import {
  QueryEditor,
  type QueryEditorHandle,
} from "@/components/calculator/query-editor";
import { OperatorToolbar } from "@/components/calculator/operator-toolbar";
import { ResultTable } from "@/components/calculator/result-table";
import { OperatorTreeView } from "@/components/calculator/operator-tree";

export function CalculatorApp() {
  const editorRef = useRef<QueryEditorHandle>(null);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [language, setLanguage] = useState<QueryLanguage>("relalg");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadDataset = useCallback(async (id: string) => {
    const detail = await getDataset(id);
    setDataset(detail);
    setResult(null);
    setError(null);
    if (language === "sql" && detail.exampleSql) {
      setQuery(detail.exampleSql);
    } else if (detail.exampleRelAlg) {
      setQuery(detail.exampleRelAlg);
    }
  }, [language]);

  const refreshDatasets = useCallback(async (selectId?: string) => {
    const list = await listDatasets();
    setDatasets(list);
    const id = selectId ?? list[0]?.id;
    if (id) await loadDataset(id);
  }, [loadDataset]);

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
    if (next === "sql" && dataset.exampleSql) {
      setQuery(dataset.exampleSql);
    } else if (next === "relalg" && dataset.exampleRelAlg) {
      setQuery(dataset.exampleRelAlg);
    }
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

  return (
    <div className="flex min-h-screen flex-col bg-[radial-gradient(ellipse_at_top,_#e8f4f2_0%,_hsl(var(--background))_55%)]">
      <header className="flex items-center justify-between border-b bg-card/80 px-4 py-3 backdrop-blur">
        <div className="flex items-center gap-4">
          <Link href="/" className="font-serif text-xl tracking-tight text-primary">
            relax
          </Link>
          <Separator orientation="vertical" className="h-5" />
          <span className="text-sm text-muted-foreground">Calculator</span>
        </div>
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
          About
        </Link>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[300px_1fr]">
        <SchemaPanel
          dataset={dataset}
          datasets={datasets}
          onSelectDataset={(id) => {
            void loadDataset(id);
          }}
          onDatasetCreated={(detail) => {
            setDatasets((prev) => {
              if (prev.some((d) => d.id === detail.id)) return prev;
              return [
                ...prev,
                { id: detail.id, name: detail.name, description: detail.description },
              ];
            });
            setDataset(detail);
            setResult(null);
            setError(null);
            const first = detail.relations[0]?.name;
            if (first) {
              setLanguage("relalg");
              setQuery(`π_{*}(${first})`);
            }
          }}
        />

        <main className="flex min-h-0 flex-col">
          <div className="space-y-3 border-b p-4">
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
              RelAlg supports classical subscripts (<code>π_&#123;a&#125;(R)</code>) and RelaX
              prefix style. Format converts to subscript notation. Shortcut: Ctrl/Cmd +
              Enter.
            </p>

            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
          </div>

          <div className="grid min-h-[320px] flex-1 grid-rows-[auto_1fr] md:grid-cols-2 md:grid-rows-1">
            <section className="flex min-h-0 flex-col border-b md:border-b-0 md:border-r">
              <div className="border-b px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Results
              </div>
              <div className="min-h-0 flex-1">
                <ResultTable result={result} />
              </div>
            </section>
            <section className="flex min-h-0 flex-col">
              <div className="border-b px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Operator tree
              </div>
              <div className="min-h-0 flex-1">
                <OperatorTreeView tree={result?.tree ?? null} />
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
