"use client";

import type { DatasetDetail } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";

type Props = {
  dataset: DatasetDetail | null;
  datasets: { id: string; name: string }[];
  onSelectDataset: (id: string) => void;
};

export function SchemaPanel({ dataset, datasets, onSelectDataset }: Props) {
  return (
    <aside className="flex h-full flex-col border-r bg-card/70">
      <div className="border-b p-3">
        <label htmlFor="dataset" className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
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
      </div>
      <ScrollArea className="flex-1 p-3">
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Relations
        </h2>
        <ul className="space-y-3">
          {dataset?.relations.map((rel) => (
            <li key={rel.name} className="rounded-md border bg-background p-2">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-semibold text-primary">{rel.name}</span>
                <span className="text-xs text-muted-foreground">{rel.rowCount} rows</span>
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
      </ScrollArea>
    </aside>
  );
}
