"use client";

import { useMemo, useState } from "react";
import type { ColumnInfo, DatasetDetail } from "@/lib/api";
import { buildRelation, uploadDataset } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Alert, AlertDescription } from "@/components/ui/alert";

type Props = {
  dataset: DatasetDetail | null;
  datasets: { id: string; name: string }[];
  onSelectDataset: (id: string) => void;
  onDatasetCreated: (detail: DatasetDetail) => void;
};

export function SchemaPanel({
  dataset,
  datasets,
  onSelectDataset,
  onDatasetCreated,
}: Props) {
  const [panel, setPanel] = useState<"schema" | "upload" | "builder">("schema");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <aside className="flex h-full flex-col border-r bg-card/70">
      <div className="border-b p-3">
        <label
          htmlFor="dataset"
          className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground"
        >
          Dataset
        </label>
        <select
          id="dataset"
          className="w-full rounded-md border bg-background px-2 py-1.5 text-sm"
          value={dataset?.id ?? ""}
          onChange={(e) => onSelectDataset(e.target.value)}
        >
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        {dataset?.description ? (
          <p className="mt-2 text-xs text-muted-foreground">{dataset.description}</p>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-1">
          <Button
            type="button"
            size="sm"
            variant={panel === "schema" ? "default" : "outline"}
            onClick={() => setPanel("schema")}
          >
            Schema
          </Button>
          <Button
            type="button"
            size="sm"
            variant={panel === "upload" ? "default" : "outline"}
            onClick={() => setPanel("upload")}
          >
            Upload
          </Button>
          <Button
            type="button"
            size="sm"
            variant={panel === "builder" ? "default" : "outline"}
            onClick={() => setPanel("builder")}
          >
            Build
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1 p-3">
        {error ? (
          <Alert variant="destructive" className="mb-3">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {panel === "schema" ? (
          <>
            <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Relations
            </h2>
            <ul className="space-y-3">
              {dataset?.relations.map((rel) => (
                <li key={rel.name} className="rounded-md border bg-background p-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-semibold text-primary">{rel.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {rel.rowCount} rows
                    </span>
                  </div>
                  <ul className="mt-1 space-y-0.5">
                    {rel.columns.map((col) => (
                      <li key={col.name} className="font-mono text-xs text-muted-foreground">
                        {col.name}
                        <span className="text-foreground/40"> : {col.type}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {panel === "upload" ? (
          <UploadPanel
            busy={busy}
            setBusy={setBusy}
            setError={setError}
            onCreated={(d) => {
              onDatasetCreated(d);
              setPanel("schema");
            }}
          />
        ) : null}

        {panel === "builder" ? (
          <BuilderPanel
            busy={busy}
            setBusy={setBusy}
            setError={setError}
            onCreated={(d) => {
              onDatasetCreated(d);
              setPanel("schema");
            }}
          />
        ) : null}
      </ScrollArea>
    </aside>
  );
}

function UploadPanel({
  busy,
  setBusy,
  setError,
  onCreated,
}: {
  busy: boolean;
  setBusy: (v: boolean) => void;
  setError: (v: string | null) => void;
  onCreated: (d: DatasetDetail) => void;
}) {
  const [relationName, setRelationName] = useState("");

  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted-foreground">
        Upload a <strong>.csv</strong> or SQLite <strong>.db</strong> file (max 5 MB).
      </p>
      <label className="block text-xs font-medium text-muted-foreground">
        Relation name (CSV only)
        <input
          className="mt-1 w-full rounded-md border bg-background px-2 py-1.5"
          value={relationName}
          onChange={(e) => setRelationName(e.target.value)}
          placeholder="People"
        />
      </label>
      <input
        type="file"
        accept=".csv,.db,.sqlite,.sqlite3"
        disabled={busy}
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          setBusy(true);
          setError(null);
          try {
            const detail = await uploadDataset(file, relationName || undefined);
            onCreated(detail);
          } catch (err) {
            setError(err instanceof Error ? err.message : "Upload failed");
          } finally {
            setBusy(false);
            e.target.value = "";
          }
        }}
      />
    </div>
  );
}

function BuilderPanel({
  busy,
  setBusy,
  setError,
  onCreated,
}: {
  busy: boolean;
  setBusy: (v: boolean) => void;
  setError: (v: string | null) => void;
  onCreated: (d: DatasetDetail) => void;
}) {
  const [name, setName] = useState("My dataset");
  const [relationName, setRelationName] = useState("R");
  const [header, setHeader] = useState("a:number, b:string");
  const [body, setBody] = useState("1, hello\n2, world");

  const preview = useMemo(() => {
    try {
      return parseBuilder(header, body);
    } catch {
      return null;
    }
  }, [header, body]);

  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted-foreground">
        Build a relation inline. Header uses <code>name:type</code> columns.
      </p>
      <label className="block text-xs font-medium text-muted-foreground">
        Dataset name
        <input
          className="mt-1 w-full rounded-md border bg-background px-2 py-1.5"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <label className="block text-xs font-medium text-muted-foreground">
        Relation name
        <input
          className="mt-1 w-full rounded-md border bg-background px-2 py-1.5"
          value={relationName}
          onChange={(e) => setRelationName(e.target.value)}
        />
      </label>
      <label className="block text-xs font-medium text-muted-foreground">
        Columns
        <input
          className="mt-1 w-full rounded-md border bg-background px-2 py-1.5 font-mono text-xs"
          value={header}
          onChange={(e) => setHeader(e.target.value)}
        />
      </label>
      <label className="block text-xs font-medium text-muted-foreground">
        Rows (CSV)
        <textarea
          className="mt-1 h-28 w-full rounded-md border bg-background px-2 py-1.5 font-mono text-xs"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
      </label>
      {preview ? (
        <p className="text-xs text-muted-foreground">
          {preview.columns.length} columns, {preview.rows.length} rows
        </p>
      ) : (
        <p className="text-xs text-destructive">Invalid table definition</p>
      )}
      <Button
        type="button"
        disabled={busy || !preview}
        onClick={async () => {
          if (!preview) return;
          setBusy(true);
          setError(null);
          try {
            const detail = await buildRelation({
              name,
              relationName,
              columns: preview.columns,
              rows: preview.rows,
            });
            onCreated(detail);
          } catch (err) {
            setError(err instanceof Error ? err.message : "Build failed");
          } finally {
            setBusy(false);
          }
        }}
      >
        Create relation
      </Button>
    </div>
  );
}

function parseBuilder(
  header: string,
  body: string,
): { columns: ColumnInfo[]; rows: unknown[][] } {
  const columns = header.split(",").map((part) => {
    const [name, type = "string"] = part.trim().split(":");
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) throw new Error("bad col");
    return { name, type: type.trim() || "string" };
  });
  const rows = body
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((line) => {
      const cells = line.split(",").map((c) => c.trim());
      if (cells.length !== columns.length) throw new Error("row width");
      return cells.map((cell, i) => {
        if (cell.toLowerCase() === "null" || cell === "") return null;
        if (columns[i].type === "number") {
          return cell.includes(".") ? Number(cell) : Number.parseInt(cell, 10);
        }
        return cell.replace(/^['"]|['"]$/g, "");
      });
    });
  return { columns, rows };
}
