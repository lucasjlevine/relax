"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { ColumnInfo, DatasetDetail } from "@/lib/api";
import { buildRelation, uploadDataset } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { FilePicker } from "@/components/ui/file-picker";

type Props = {
  dataset: DatasetDetail | null;
  datasets: { id: string; name: string }[];
  onSelectDataset: (id: string) => void;
  onDatasetCreated: (detail: DatasetDetail) => void;
};

const COL_TYPES = ["string", "number", "boolean", "date"] as const;

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
        <Label htmlFor="dataset">Dataset</Label>
        <select
          id="dataset"
          className="mt-1 w-full rounded-md border bg-background px-2 py-1.5 text-sm"
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
          {(
            [
              ["schema", "Schema"],
              ["upload", "Upload"],
              ["builder", "Build"],
            ] as const
          ).map(([id, label]) => (
            <Button
              key={id}
              type="button"
              size="sm"
              variant={panel === id ? "default" : "outline"}
              onClick={() => {
                setError(null);
                setPanel(id);
              }}
            >
              {label}
            </Button>
          ))}
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
  const [file, setFile] = useState<File | null>(null);
  const [relationName, setRelationName] = useState("");
  const [hasHeader, setHasHeader] = useState(true);
  const [skipRows, setSkipRows] = useState(0);
  const [delimiter, setDelimiter] = useState(",");
  const isCsv = file?.name.toLowerCase().endsWith(".csv") ?? true;

  return (
    <div className="space-y-4 text-sm">
      <div>
        <p className="mb-2 text-muted-foreground">
          Import a CSV or SQLite database (max 5 MB).
        </p>
        <FilePicker
          accept=".csv,.db,.sqlite,.sqlite3"
          disabled={busy}
          file={file}
          onFileChange={setFile}
          label="Drop a file or browse"
          hint=".csv, .db, .sqlite"
        />
      </div>

      {isCsv ? (
        <div className="space-y-3 rounded-md border bg-background p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            CSV options
          </p>
          <div className="space-y-1">
            <Label htmlFor="rel-name">Relation name</Label>
            <Input
              id="rel-name"
              value={relationName}
              onChange={(e) => setRelationName(e.target.value)}
              placeholder="People"
            />
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="has-header"
              checked={hasHeader}
              onCheckedChange={(v) => setHasHeader(v === true)}
            />
            <Label htmlFor="has-header" className="cursor-pointer text-foreground">
              First row is header
            </Label>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label htmlFor="skip-rows">Skip rows</Label>
              <Input
                id="skip-rows"
                type="number"
                min={0}
                value={skipRows}
                onChange={(e) => setSkipRows(Number(e.target.value) || 0)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="delimiter">Delimiter</Label>
              <select
                id="delimiter"
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={delimiter}
                onChange={(e) => setDelimiter(e.target.value)}
              >
                <option value=",">Comma (,)</option>
                <option value=";">Semicolon (;)</option>
                <option value={"\t"}>Tab</option>
                <option value="|">Pipe (|)</option>
              </select>
            </div>
          </div>
        </div>
      ) : null}

      <Button
        type="button"
        className="w-full"
        disabled={busy || !file}
        onClick={async () => {
          if (!file) return;
          setBusy(true);
          setError(null);
          try {
            const detail = await uploadDataset(file, {
              relationName: relationName || undefined,
              hasHeader,
              skipRows,
              delimiter,
            });
            onCreated(detail);
          } catch (err) {
            setError(err instanceof Error ? err.message : "Upload failed");
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Uploading…" : "Upload dataset"}
      </Button>
    </div>
  );
}

type ColDraft = { name: string; type: string };
type RowDraft = string[];

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
  const [columns, setColumns] = useState<ColDraft[]>([
    { name: "a", type: "number" },
    { name: "b", type: "string" },
  ]);
  const [rows, setRows] = useState<RowDraft[]>([
    ["1", "hello"],
    ["2", "world"],
  ]);

  const syncRowWidth = (cols: ColDraft[], current: RowDraft[]) =>
    current.map((row) => {
      const next = [...row];
      while (next.length < cols.length) next.push("");
      return next.slice(0, cols.length);
    });

  const valid =
    relationName.trim().length > 0 &&
    columns.length > 0 &&
    columns.every((c) => /^[A-Za-z_][A-Za-z0-9_]*$/.test(c.name));

  return (
    <div className="space-y-4 text-sm">
      <p className="text-muted-foreground">
        Define columns and fill cells — no raw CSV typing required.
      </p>

      <div className="space-y-1">
        <Label htmlFor="ds-name">Dataset name</Label>
        <Input id="ds-name" value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="rel">Relation name</Label>
        <Input
          id="rel"
          value={relationName}
          onChange={(e) => setRelationName(e.target.value)}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Columns</Label>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              const next = [
                ...columns,
                { name: `col${columns.length + 1}`, type: "string" },
              ];
              setColumns(next);
              setRows(syncRowWidth(next, rows));
            }}
          >
            <Plus className="h-3.5 w-3.5" />
            Add column
          </Button>
        </div>
        <ul className="space-y-2">
          {columns.map((col, i) => (
            <li key={i} className="flex items-center gap-2">
              <Input
                value={col.name}
                aria-label={`Column ${i + 1} name`}
                onChange={(e) => {
                  const next = columns.map((c, j) =>
                    j === i ? { ...c, name: e.target.value } : c,
                  );
                  setColumns(next);
                }}
              />
              <select
                className="h-9 rounded-md border bg-background px-2 text-sm"
                value={col.type}
                aria-label={`Column ${i + 1} type`}
                onChange={(e) => {
                  const next = columns.map((c, j) =>
                    j === i ? { ...c, type: e.target.value } : c,
                  );
                  setColumns(next);
                }}
              >
                {COL_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label={`Remove column ${col.name}`}
                disabled={columns.length <= 1}
                onClick={() => {
                  const next = columns.filter((_, j) => j !== i);
                  setColumns(next);
                  setRows(syncRowWidth(next, rows));
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Rows</Label>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setRows([...rows, columns.map(() => "")])}
          >
            <Plus className="h-3.5 w-3.5" />
            Add row
          </Button>
        </div>
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full min-w-[220px] text-xs">
            <thead>
              <tr className="border-b bg-muted/50">
                {columns.map((c) => (
                  <th key={c.name} className="px-2 py-1.5 text-left font-medium">
                    {c.name || "…"}
                  </th>
                ))}
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="border-b last:border-0">
                  {columns.map((_, ci) => (
                    <td key={ci} className="p-1">
                      <Input
                        className="h-8 font-mono text-xs"
                        value={row[ci] ?? ""}
                        onChange={(e) => {
                          const next = rows.map((r, j) => {
                            if (j !== ri) return r;
                            const copy = [...r];
                            copy[ci] = e.target.value;
                            return copy;
                          });
                          setRows(next);
                        }}
                      />
                    </td>
                  ))}
                  <td className="p-1">
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      aria-label={`Remove row ${ri + 1}`}
                      onClick={() => setRows(rows.filter((_, j) => j !== ri))}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Button
        type="button"
        className="w-full"
        disabled={busy || !valid}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            const cols: ColumnInfo[] = columns.map((c) => ({
              name: c.name,
              type: c.type,
            }));
            const parsedRows = rows.map((row) =>
              row.map((cell, i) => {
                const raw = cell.trim();
                if (raw === "" || raw.toLowerCase() === "null") return null;
                if (cols[i].type === "number") {
                  return raw.includes(".") ? Number(raw) : Number.parseInt(raw, 10);
                }
                if (cols[i].type === "boolean") {
                  return ["true", "1", "yes", "t"].includes(raw.toLowerCase());
                }
                return raw;
              }),
            );
            const detail = await buildRelation({
              name,
              relationName,
              columns: cols,
              rows: parsedRows,
            });
            onCreated(detail);
          } catch (err) {
            setError(err instanceof Error ? err.message : "Build failed");
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Creating…" : "Create relation"}
      </Button>
    </div>
  );
}
