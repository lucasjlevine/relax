"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Play } from "lucide-react";
import {
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

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await listDatasets();
        if (cancelled) return;
        setDatasets(list);
        if (list[0]) {
          await loadDataset(list[0].id);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load datasets");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

      <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[260px_1fr]">
        <SchemaPanel
          dataset={dataset}
          datasets={datasets}
          onSelectDataset={(id) => {
            void loadDataset(id);
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
              <Button onClick={() => void execute()} disabled={loading || !dataset}>
                <Play className="h-4 w-4" aria-hidden />
                {loading ? "Running…" : "Execute"}
              </Button>
            </div>

            {language === "relalg" ? (
              <OperatorToolbar
                onInsert={(text) => editorRef.current?.insertAtCursor(text)}
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
              Shortcut: Ctrl/Cmd + Enter to execute
            </p>

            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Query error</AlertTitle>
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
