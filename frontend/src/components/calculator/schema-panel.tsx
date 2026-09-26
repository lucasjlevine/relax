"use client";

import { useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import type { ColumnInfo, DatasetDetail, RelationData } from "@/lib/api";
import {
  addRelation,
  addRelationRow,
  addColumn,
  buildRelation,
  deleteColumn,
  deleteDataset,
  deleteRelation,
  deleteRelationRow,
  getRelation,
  changeColumnType,
  renameColumn,
  renameDataset,
  renameRelation,
  updateRelationRow,
  uploadDataset,
  uploadRelationCsv,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { FilePicker } from "@/components/ui/file-picker";

export type SchemaPanelTab = "schema" | "manage" | "upload" | "builder";

type Props = {
  dataset: DatasetDetail | null;
  datasets: { id: string; name: string }[];
  activeTab: SchemaPanelTab;
  onTabChange: (tab: SchemaPanelTab) => void;
  onSelectDataset: (id: string) => void;
  onDatasetCreated: (detail: DatasetDetail) => void;
  onDatasetUpdated: (detail: DatasetDetail) => void;
  onDatasetDeleted: (id: string) => void | Promise<void>;
};

const COL_TYPES = ["string", "number", "boolean", "date"] as const;

export function SchemaPanel({
  dataset,
  datasets,
  activeTab,
  onTabChange,
  onSelectDataset,
  onDatasetCreated,
  onDatasetUpdated,
  onDatasetDeleted,
}: Props) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const panel = activeTab;

  const switchTab = (id: SchemaPanelTab) => {
    setError(null);
    onTabChange(id);
  };

  return (
    <aside className="flex h-full min-h-0 w-full flex-col overflow-hidden">
      <div className="shrink-0 border-b p-3">
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
              ["manage", "Manage"],
              ["upload", "Upload"],
              ["builder", "Build"],
            ] as const
          ).map(([id, label]) => (
            <Button
              key={id}
              type="button"
              size="sm"
              variant={panel === id ? "default" : "outline"}
              onClick={() => switchTab(id)}
            >
              {label}
            </Button>
          ))}
        </div>
        {panel === "manage" ? (
          <p className="mt-2 text-[11px] leading-snug text-muted-foreground">
            Drag the panel edge to widen it, or scroll horizontally for wide tables.
          </p>
        ) : null}
      </div>

      <div className="min-h-0 min-w-0 flex-1 overflow-auto p-3">
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

        {panel === "manage" && dataset ? (
          <ManagePanel
            dataset={dataset}
            busy={busy}
            setBusy={setBusy}
            setError={setError}
            onUpdated={onDatasetUpdated}
            onDeleted={onDatasetDeleted}
          />
        ) : null}

        {panel === "manage" && !dataset ? (
          <p className="text-sm text-muted-foreground">Select a dataset to manage.</p>
        ) : null}

        {panel === "upload" ? (
          <UploadPanel
            busy={busy}
            setBusy={setBusy}
            setError={setError}
            onCreated={(d) => {
              onDatasetCreated(d);
              switchTab("schema");
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
              switchTab("schema");
            }}
          />
        ) : null}
      </div>
    </aside>
  );
}

function ManagePanel({
  dataset,
  busy,
  setBusy,
  setError,
  onUpdated,
  onDeleted,
}: {
  dataset: DatasetDetail;
  busy: boolean;
  setBusy: (v: boolean) => void;
  setError: (v: string | null) => void;
  onUpdated: (d: DatasetDetail) => void;
  onDeleted: (id: string) => void | Promise<void>;
}) {
  const [nameDraft, setNameDraft] = useState(dataset.name);
  const [activeRel, setActiveRel] = useState(dataset.relations[0]?.name ?? "");
  const [relNameDraft, setRelNameDraft] = useState(activeRel);
  const [relation, setRelation] = useState<RelationData | null>(null);
  const [rowDrafts, setRowDrafts] = useState<string[][]>([]);
  const [newRow, setNewRow] = useState<string[]>([]);
  const [colDrafts, setColDrafts] = useState<string[]>([]);
  const [showAddRel, setShowAddRel] = useState(false);
  const [newRelName, setNewRelName] = useState("R2");
  const [newRelCols, setNewRelCols] = useState<{ name: string; type: string }[]>([
    { name: "id", type: "number" },
    { name: "label", type: "string" },
  ]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvRelName, setCsvRelName] = useState("");

  const refreshRelation = async (relName: string) => {
    const refreshed = await getRelation(dataset.id, relName);
    setRelation(refreshed);
    setRowDrafts(
      refreshed.rows.map((r) => r.map((cell) => (cell == null ? "" : String(cell)))),
    );
    setNewRow(refreshed.columns.map(() => ""));
    setColDrafts(refreshed.columns.map((c) => c.name));
    setRelNameDraft(refreshed.name);
  };

  useEffect(() => {
    setNameDraft(dataset.name);
  }, [dataset.name]);

  useEffect(() => {
    const stillThere = dataset.relations.some((r) => r.name === activeRel);
    if (!stillThere) {
      const next = dataset.relations[0]?.name ?? "";
      setActiveRel(next);
      setRelNameDraft(next);
    }
  }, [dataset.relations, activeRel]);

  useEffect(() => {
    if (!activeRel) {
      setRelation(null);
      setRowDrafts([]);
      setNewRow([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await getRelation(dataset.id, activeRel);
        if (cancelled) return;
        setRelation(data);
        setRowDrafts(
          data.rows.map((row) => row.map((cell) => (cell == null ? "" : String(cell)))),
        );
        setNewRow(data.columns.map(() => ""));
        setColDrafts(data.columns.map((c) => c.name));
        setRelNameDraft(data.name);
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load relation");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [dataset.id, activeRel, setError]);

  const parseCell = (raw: string, type: string): unknown => {
    const trimmed = raw.trim();
    if (trimmed === "" || trimmed.toLowerCase() === "null") return null;
    if (type === "number") {
      const cleaned = trimmed
        .replace(/^(?:A\$|C\$|US\$|AUD|USD|CAD|EUR|GBP)\s*/i, "")
        .replace(/[$€£¥₹₩]/g, "")
        .replace(/,/g, "")
        .replace(/\s/g, "")
        .replace(/%$/, "");
      if (!cleaned) return null;
      return cleaned.includes(".") || /e/i.test(cleaned)
        ? Number(cleaned)
        : Number.parseInt(cleaned, 10);
    }
    if (type === "boolean") {
      return ["true", "1", "yes", "t"].includes(trimmed.toLowerCase());
    }
    return trimmed;
  };

  return (
    <div className="min-w-0 space-y-4 text-sm">
      <div className="space-y-2 rounded-md border bg-background p-3">
        <Label htmlFor="rename-ds">Dataset name</Label>
        <div className="flex gap-2">
          <Input
            id="rename-ds"
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
          />
          <Button
            type="button"
            size="sm"
            disabled={busy || !nameDraft.trim() || nameDraft === dataset.name}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                onUpdated(await renameDataset(dataset.id, nameDraft.trim()));
              } catch (err) {
                setError(err instanceof Error ? err.message : "Rename failed");
              } finally {
                setBusy(false);
              }
            }}
          >
            <Pencil className="h-3.5 w-3.5" />
            Save
          </Button>
        </div>
        <Button
          type="button"
          size="sm"
          variant="destructive"
          className="w-full"
          disabled={busy}
          onClick={async () => {
            if (!window.confirm(`Delete dataset “${dataset.name}”?`)) return;
            setBusy(true);
            setError(null);
            try {
              await deleteDataset(dataset.id);
              await onDeleted(dataset.id);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Delete failed");
            } finally {
              setBusy(false);
            }
          }}
        >
          <Trash2 className="h-3.5 w-3.5" />
          Delete dataset
        </Button>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor="rel-pick">Relation</Label>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setShowAddRel((v) => !v)}
          >
            <Plus className="h-3.5 w-3.5" />
            Add relation
          </Button>
        </div>
        <select
          id="rel-pick"
          className="w-full rounded-md border bg-background px-2 py-1.5 text-sm"
          value={activeRel}
          onChange={(e) => setActiveRel(e.target.value)}
        >
          {dataset.relations.map((r) => (
            <option key={r.name} value={r.name}>
              {r.name} ({r.rowCount})
            </option>
          ))}
        </select>
      </div>

      {showAddRel ? (
        <div className="space-y-3 rounded-md border bg-background p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Add relation to this dataset
          </p>
          <div className="space-y-1">
            <Label htmlFor="new-rel">Name</Label>
            <Input
              id="new-rel"
              value={newRelName}
              onChange={(e) => setNewRelName(e.target.value)}
            />
          </div>
          <ul className="space-y-2">
            {newRelCols.map((col, i) => (
              <li key={i} className="flex items-center gap-2">
                <Input
                  value={col.name}
                  aria-label={`New column ${i + 1} name`}
                  onChange={(e) => {
                    setNewRelCols((prev) =>
                      prev.map((c, j) =>
                        j === i ? { ...c, name: e.target.value } : c,
                      ),
                    );
                  }}
                />
                <select
                  className="h-9 rounded-md border bg-background px-2 text-sm"
                  value={col.type}
                  aria-label={`New column ${i + 1} type`}
                  onChange={(e) => {
                    setNewRelCols((prev) =>
                      prev.map((c, j) =>
                        j === i ? { ...c, type: e.target.value } : c,
                      ),
                    );
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
                  disabled={newRelCols.length <= 1}
                  aria-label={`Remove column ${col.name}`}
                  onClick={() =>
                    setNewRelCols((prev) => prev.filter((_, j) => j !== i))
                  }
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </li>
            ))}
          </ul>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() =>
              setNewRelCols((prev) => [
                ...prev,
                { name: `col${prev.length + 1}`, type: "string" },
              ])
            }
          >
            <Plus className="h-3.5 w-3.5" />
            Column
          </Button>
          <Button
            type="button"
            className="w-full"
            disabled={
              busy ||
              !/^[A-Za-z_][A-Za-z0-9_]*$/.test(newRelName) ||
              newRelCols.some((c) => !/^[A-Za-z_][A-Za-z0-9_]*$/.test(c.name))
            }
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                const detail = await addRelation(dataset.id, {
                  relationName: newRelName,
                  columns: newRelCols.map((c) => ({
                    name: c.name,
                    type: c.type,
                  })),
                });
                onUpdated(detail);
                setActiveRel(newRelName);
                setShowAddRel(false);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Add failed");
              } finally {
                setBusy(false);
              }
            }}
          >
            Create empty relation
          </Button>

          <div className="space-y-2 border-t pt-3">
            <p className="text-xs text-muted-foreground">
              Or import another CSV into this dataset
            </p>
            <FilePicker
              accept=".csv"
              disabled={busy}
              file={csvFile}
              onFileChange={setCsvFile}
              label="Drop a CSV or browse"
              hint=".csv only"
            />
            <Input
              value={csvRelName}
              onChange={(e) => setCsvRelName(e.target.value)}
              placeholder="Relation name (optional)"
            />
            <Button
              type="button"
              className="w-full"
              disabled={busy || !csvFile}
              onClick={async () => {
                if (!csvFile) return;
                setBusy(true);
                setError(null);
                try {
                  const before = new Set(dataset.relations.map((r) => r.name));
                  const detail = await uploadRelationCsv(dataset.id, csvFile, {
                    relationName: csvRelName || undefined,
                  });
                  onUpdated(detail);
                  const added =
                    detail.relations.find((r) => !before.has(r.name))?.name ??
                    detail.relations[detail.relations.length - 1]?.name;
                  if (added) setActiveRel(added);
                  setCsvFile(null);
                  setCsvRelName("");
                  setShowAddRel(false);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Upload failed");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Import CSV as relation
            </Button>
          </div>
        </div>
      ) : null}

      {relation ? (
        <div className="space-y-3 rounded-md border bg-background p-3">
          <div className="flex gap-2">
            <Input
              value={relNameDraft}
              onChange={(e) => setRelNameDraft(e.target.value)}
              aria-label="Relation name"
            />
            <Button
              type="button"
              size="sm"
              disabled={
                busy || !relNameDraft.trim() || relNameDraft === relation.name
              }
              onClick={async () => {
                setBusy(true);
                setError(null);
                try {
                  const detail = await renameRelation(
                    dataset.id,
                    relation.name,
                    relNameDraft.trim(),
                  );
                  onUpdated(detail);
                  setActiveRel(relNameDraft.trim());
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Rename failed");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Rename
            </Button>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="w-full"
            disabled={busy || dataset.relations.length <= 1}
            onClick={async () => {
              if (!window.confirm(`Delete relation “${relation.name}”?`)) return;
              setBusy(true);
              setError(null);
              try {
                const detail = await deleteRelation(dataset.id, relation.name);
                onUpdated(detail);
                setActiveRel(detail.relations[0]?.name ?? "");
              } catch (err) {
                setError(err instanceof Error ? err.message : "Delete failed");
              } finally {
                setBusy(false);
              }
            }}
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete relation
          </Button>

          <div className="max-w-full overflow-x-auto rounded-md border">
            <table className="w-max min-w-full text-xs">
              <thead>
                <tr className="border-b bg-muted/50">
                  {relation.columns.map((c, ci) => (
                    <th
                      key={c.name}
                      className="whitespace-nowrap px-1 py-1.5 text-left font-medium"
                    >
                      <div className="flex min-w-[8rem] items-center gap-1">
                        <Input
                          className="h-7 font-mono text-xs"
                          value={colDrafts[ci] ?? c.name}
                          aria-label={`Rename column ${c.name}`}
                          onChange={(e) => {
                            const value = e.target.value;
                            setColDrafts((prev) => {
                              const next = [...prev];
                              next[ci] = value;
                              return next;
                            });
                          }}
                          onBlur={async () => {
                            const next = (colDrafts[ci] ?? "").trim();
                            if (!next || next === c.name) {
                              setColDrafts(relation.columns.map((col) => col.name));
                              return;
                            }
                            setBusy(true);
                            setError(null);
                            try {
                              const detail = await renameColumn(
                                dataset.id,
                                relation.name,
                                c.name,
                                next,
                              );
                              onUpdated(detail);
                              await refreshRelation(relation.name);
                            } catch (err) {
                              setColDrafts(relation.columns.map((col) => col.name));
                              setError(
                                err instanceof Error
                                  ? err.message
                                  : "Rename column failed",
                              );
                            } finally {
                              setBusy(false);
                            }
                          }}
                        />
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 shrink-0"
                          disabled={busy || relation.columns.length <= 1}
                          aria-label={`Delete column ${c.name}`}
                          onClick={async () => {
                            if (
                              !window.confirm(
                                `Delete column “${c.name}” from ${relation.name}?`,
                              )
                            ) {
                              return;
                            }
                            setBusy(true);
                            setError(null);
                            try {
                              const detail = await deleteColumn(
                                dataset.id,
                                relation.name,
                                c.name,
                              );
                              onUpdated(detail);
                              await refreshRelation(relation.name);
                            } catch (err) {
                              setError(
                                err instanceof Error
                                  ? err.message
                                  : "Delete column failed",
                              );
                            } finally {
                              setBusy(false);
                            }
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                      <span className="mt-0.5 block px-1">
                        <select
                          className="h-7 w-full min-w-[5.5rem] rounded border bg-background px-1 text-[11px] font-normal text-muted-foreground"
                          value={c.type}
                          aria-label={`Type for column ${c.name}`}
                          disabled={busy}
                          onChange={async (e) => {
                            const nextType = e.target.value;
                            if (nextType === c.type) return;
                            setBusy(true);
                            setError(null);
                            try {
                              const detail = await changeColumnType(
                                dataset.id,
                                relation.name,
                                c.name,
                                nextType,
                              );
                              onUpdated(detail);
                              await refreshRelation(relation.name);
                            } catch (err) {
                              setError(
                                err instanceof Error
                                  ? err.message
                                  : "Change type failed",
                              );
                            } finally {
                              setBusy(false);
                            }
                          }}
                        >
                          {COL_TYPES.map((t) => (
                            <option key={t} value={t}>
                              {t}
                            </option>
                          ))}
                        </select>
                      </span>
                    </th>
                  ))}
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {rowDrafts.map((row, ri) => (
                  <tr key={ri} className="border-b last:border-0">
                    {relation.columns.map((col, ci) => (
                      <td key={col.name} className="p-1">
                        <Input
                          className="h-8 min-w-[7rem] font-mono text-xs"
                          value={row[ci] ?? ""}
                          onChange={(e) => {
                            setRowDrafts((prev) =>
                              prev.map((r, j) => {
                                if (j !== ri) return r;
                                const copy = [...r];
                                copy[ci] = e.target.value;
                                return copy;
                              }),
                            );
                          }}
                          onBlur={async () => {
                            const values = row.map((cell, i) =>
                              parseCell(cell, relation.columns[i].type),
                            );
                            const original = relation.rows[ri] ?? [];
                            const same =
                              values.length === original.length &&
                              values.every(
                                (v, i) =>
                                  String(v ?? "") === String(original[i] ?? ""),
                              );
                            if (same) return;
                            setBusy(true);
                            setError(null);
                            try {
                              const detail = await updateRelationRow(
                                dataset.id,
                                relation.name,
                                ri,
                                values,
                              );
                              onUpdated(detail);
                              await refreshRelation(relation.name);
                            } catch (err) {
                              setError(
                                err instanceof Error
                                  ? err.message
                                  : "Update failed",
                              );
                            } finally {
                              setBusy(false);
                            }
                          }}
                        />
                      </td>
                    ))}
                    <td className="p-1">
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        aria-label={`Delete row ${ri + 1}`}
                        disabled={busy}
                        onClick={async () => {
                          setBusy(true);
                          setError(null);
                          try {
                            const detail = await deleteRelationRow(
                              dataset.id,
                              relation.name,
                              ri,
                            );
                            onUpdated(detail);
                            await refreshRelation(relation.name);
                          } catch (err) {
                            setError(
                              err instanceof Error
                                ? err.message
                                : "Delete failed",
                            );
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
                <tr className="bg-muted/20">
                  {relation.columns.map((col, ci) => (
                    <td key={col.name} className="p-1">
                      <Input
                        className="h-8 min-w-[7rem] font-mono text-xs"
                        placeholder={col.name}
                        value={newRow[ci] ?? ""}
                        onChange={(e) => {
                          setNewRow((prev) => {
                            const copy = [...prev];
                            copy[ci] = e.target.value;
                            return copy;
                          });
                        }}
                      />
                    </td>
                  ))}
                  <td className="p-1">
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      aria-label="Add row"
                      disabled={busy}
                      onClick={async () => {
                        const values = relation.columns.map((col, i) =>
                          parseCell(newRow[i] ?? "", col.type),
                        );
                        setBusy(true);
                        setError(null);
                        try {
                          const detail = await addRelationRow(
                            dataset.id,
                            relation.name,
                            values,
                          );
                          onUpdated(detail);
                          await refreshRelation(relation.name);
                          setNewRow(relation.columns.map(() => ""));
                        } catch (err) {
                          setError(
                            err instanceof Error ? err.message : "Add failed",
                          );
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      <Plus className="h-3.5 w-3.5" />
                    </Button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="w-full"
            disabled={busy}
            onClick={async () => {
              const base = "col";
              let n = relation.columns.length + 1;
              let name = `${base}${n}`;
              const existing = new Set(relation.columns.map((c) => c.name));
              while (existing.has(name)) {
                n += 1;
                name = `${base}${n}`;
              }
              setBusy(true);
              setError(null);
              try {
                const detail = await addColumn(dataset.id, relation.name, {
                  name,
                  type: "string",
                });
                onUpdated(detail);
                await refreshRelation(relation.name);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Add column failed");
              } finally {
                setBusy(false);
              }
            }}
          >
            <Plus className="h-3.5 w-3.5" />
            Add column
          </Button>
        </div>
      ) : null}
    </div>
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
        <div className="max-w-full overflow-x-auto rounded-md border">
          <table className="w-max min-w-full text-xs">
            <thead>
              <tr className="border-b bg-muted/50">
                {columns.map((c) => (
                  <th
                    key={c.name}
                    className="whitespace-nowrap px-2 py-1.5 text-left font-medium"
                  >
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
                        className="h-8 min-w-[7rem] font-mono text-xs"
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
