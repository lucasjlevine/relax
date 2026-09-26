const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ColumnInfo = { name: string; type: string };
export type RelationInfo = {
  name: string;
  columns: ColumnInfo[];
  rowCount: number;
};
export type DatasetSummary = {
  id: string;
  name: string;
  description: string;
};
export type DatasetDetail = DatasetSummary & {
  relations: RelationInfo[];
  exampleRelAlg?: string | null;
  exampleSql?: string | null;
};
export type RelationData = {
  name: string;
  columns: ColumnInfo[];
  rows: unknown[][];
};
export type OperatorTreeNode = {
  id: string;
  label: string;
  operator: string;
  children: OperatorTreeNode[];
};
export type QueryResponse = {
  columns: ColumnInfo[];
  rows: unknown[][];
  rowCount: number;
  executionMs: number;
  tree: OperatorTreeNode | null;
  warnings: string[];
};
export type QueryLanguage = "relalg" | "sql";

export type UploadOptions = {
  relationName?: string;
  hasHeader?: boolean;
  skipRows?: number;
  delimiter?: string;
};

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      const detail = body?.detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (detail?.message) {
        message = detail.message;
      } else if (Array.isArray(detail)) {
        message = detail
          .map((d: { msg?: string }) => d?.msg)
          .filter(Boolean)
          .join("; ") || message;
      }
    } catch {
      /* ignore */
    }
    throw new Error(typeof message === "string" ? message : "Request failed");
  }
  return res.json() as Promise<T>;
}

export async function listDatasets(): Promise<DatasetSummary[]> {
  const data = await handle<{ datasets: DatasetSummary[] }>(
    await fetch(`${API_URL}/api/datasets`, { cache: "no-store" }),
  );
  return data.datasets;
}

export async function getDataset(id: string): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(`${API_URL}/api/datasets/${id}`, { cache: "no-store" }),
  );
}

export async function renameDataset(
  id: string,
  name: string,
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(`${API_URL}/api/datasets/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  );
}

export async function deleteDataset(id: string): Promise<void> {
  await handle<{ ok: boolean }>(
    await fetch(`${API_URL}/api/datasets/${id}`, { method: "DELETE" }),
  );
}

export async function getRelation(
  datasetId: string,
  relationName: string,
): Promise<RelationData> {
  return handle<RelationData>(
    await fetch(
      `${API_URL}/api/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}`,
      { cache: "no-store" },
    ),
  );
}

export async function renameRelation(
  datasetId: string,
  relationName: string,
  name: string,
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(
      `${API_URL}/api/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      },
    ),
  );
}

export async function deleteRelation(
  datasetId: string,
  relationName: string,
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(
      `${API_URL}/api/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}`,
      { method: "DELETE" },
    ),
  );
}

export async function addRelation(
  datasetId: string,
  input: {
    relationName: string;
    columns: ColumnInfo[];
    rows?: unknown[][];
  },
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(`${API_URL}/api/datasets/${datasetId}/relations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        relationName: input.relationName,
        columns: input.columns,
        rows: input.rows ?? [],
      }),
    }),
  );
}

export async function uploadRelationCsv(
  datasetId: string,
  file: File,
  options: UploadOptions = {},
): Promise<DatasetDetail> {
  const form = new FormData();
  form.append("file", file);
  if (options.relationName) form.append("relationName", options.relationName);
  form.append("hasHeader", String(options.hasHeader ?? true));
  form.append("skipRows", String(options.skipRows ?? 0));
  form.append("delimiter", options.delimiter ?? ",");
  return handle<DatasetDetail>(
    await fetch(`${API_URL}/api/datasets/${datasetId}/upload`, {
      method: "POST",
      body: form,
    }),
  );
}

export async function renameColumn(
  datasetId: string,
  relationName: string,
  columnName: string,
  name: string,
): Promise<DatasetDetail> {
  return updateColumn(datasetId, relationName, columnName, { name });
}

export async function changeColumnType(
  datasetId: string,
  relationName: string,
  columnName: string,
  type: string,
): Promise<DatasetDetail> {
  return updateColumn(datasetId, relationName, columnName, { type });
}

export async function updateColumn(
  datasetId: string,
  relationName: string,
  columnName: string,
  patch: { name?: string; type?: string },
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(
      `${API_URL}/api/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/columns/${encodeURIComponent(columnName)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      },
    ),
  );
}

export async function deleteColumn(
  datasetId: string,
  relationName: string,
  columnName: string,
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(
      `${API_URL}/api/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/columns/${encodeURIComponent(columnName)}`,
      { method: "DELETE" },
    ),
  );
}

export async function addColumn(
  datasetId: string,
  relationName: string,
  input: { name: string; type?: string; default?: unknown },
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(
      `${API_URL}/api/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/columns`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: input.name,
          type: input.type ?? "string",
          default: input.default ?? null,
        }),
      },
    ),
  );
}

export async function addRelationRow(
  datasetId: string,
  relationName: string,
  values: unknown[],
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(
      `${API_URL}/api/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/rows`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values }),
      },
    ),
  );
}

export async function updateRelationRow(
  datasetId: string,
  relationName: string,
  rowIndex: number,
  values: unknown[],
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(
      `${API_URL}/api/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/rows/${rowIndex}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values }),
      },
    ),
  );
}

export async function deleteRelationRow(
  datasetId: string,
  relationName: string,
  rowIndex: number,
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(
      `${API_URL}/api/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/rows/${rowIndex}`,
      { method: "DELETE" },
    ),
  );
}

export async function setRelationRows(
  datasetId: string,
  relationName: string,
  rows: unknown[][],
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(
      `${API_URL}/api/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/rows`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rows }),
      },
    ),
  );
}

export async function runQuery(input: {
  datasetId: string;
  language: QueryLanguage;
  query: string;
  limit?: number;
  offset?: number;
}): Promise<QueryResponse> {
  return handle<QueryResponse>(
    await fetch(`${API_URL}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function formatQuery(input: {
  language: QueryLanguage;
  query: string;
}): Promise<string> {
  const data = await handle<{ formatted: string }>(
    await fetch(`${API_URL}/api/format`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
  return data.formatted;
}

export async function uploadDataset(
  file: File,
  options: UploadOptions = {},
): Promise<DatasetDetail> {
  const form = new FormData();
  form.append("file", file);
  if (options.relationName) form.append("relationName", options.relationName);
  form.append("hasHeader", String(options.hasHeader ?? true));
  form.append("skipRows", String(options.skipRows ?? 0));
  form.append("delimiter", options.delimiter ?? ",");
  return handle<DatasetDetail>(
    await fetch(`${API_URL}/api/datasets/upload`, {
      method: "POST",
      body: form,
    }),
  );
}

export async function buildRelation(input: {
  name: string;
  relationName: string;
  columns: ColumnInfo[];
  rows: unknown[][];
}): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await fetch(`${API_URL}/api/datasets/build`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export function resultsToCsv(result: QueryResponse): string {
  const escape = (value: unknown): string => {
    if (value === null || value === undefined) return "";
    const text = String(value);
    if (/[",\n\r]/.test(text)) {
      return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
  };
  const header = result.columns.map((c) => escape(c.name)).join(",");
  const lines = result.rows.map((row) => row.map(escape).join(","));
  return [header, ...lines].join("\n");
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
