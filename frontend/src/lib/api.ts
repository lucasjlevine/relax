/** Full API root including path prefix (local /api, Silk /relax-api). */
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

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
  owned?: boolean;
  isBuiltin?: boolean;
};
export type DatasetDetail = DatasetSummary & {
  relations: RelationInfo[];
  exampleRelAlg?: string | null;
  exampleSql?: string | null;
  shareToken?: string | null;
  forkedFrom?: string | null;
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
export type QueryResultBlock = {
  index: number;
  label?: string | null;
  columns: ColumnInfo[];
  rows: unknown[][];
  rowCount: number;
  executionMs: number;
  tree: OperatorTreeNode | null;
  warnings: string[];
};
export type TypeChangeInfo = {
  relation: string;
  column: string;
  fromType: string;
  toType: string;
};
export type QueryResponse = {
  columns: ColumnInfo[];
  rows: unknown[][];
  rowCount: number;
  executionMs: number;
  tree: OperatorTreeNode | null;
  warnings: string[];
  results?: QueryResultBlock[];
  datasetId?: string | null;
  typeChanges?: TypeChangeInfo[];
};
export type QueryLanguage = "relalg" | "sql";

export type ApiErrorCode =
  | "validation_error"
  | "parse_error"
  | "compile_error"
  | "execution_error"
  | "format_error"
  | "not_found"
  | "dataset_error"
  | "upload_error"
  | "build_error"
  | "query_error"
  | string;

export class ApiError extends Error {
  code: ApiErrorCode;
  constructor(message: string, code: ApiErrorCode = "query_error") {
    super(message);
    this.name = "ApiError";
    this.code = code;
  }
}

export type UploadOptions = {
  relationName?: string;
  hasHeader?: boolean;
  skipRows?: number;
  delimiter?: string;
};

async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  return fetch(input, {
    ...init,
    credentials: "include",
    cache: init.cache ?? "no-store",
  });
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = res.statusText;
    let code: ApiErrorCode = "query_error";
    try {
      const body = await res.json();
      const detail = body?.detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (detail?.message) {
        message = detail.message;
        if (typeof detail.code === "string") code = detail.code;
      } else if (Array.isArray(detail)) {
        message =
          detail
            .map((d: { msg?: string }) => d?.msg)
            .filter(Boolean)
            .join("; ") || message;
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(
      typeof message === "string" ? message : "Request failed",
      code,
    );
  }
  return res.json() as Promise<T>;
}

export function errorTitle(err: unknown, fallback = "Couldn’t run query"): string {
  if (!(err instanceof ApiError)) return fallback;
  switch (err.code) {
    case "parse_error":
    case "format_error":
      return "Syntax error";
    case "compile_error":
      return "Couldn’t compile query";
    case "execution_error":
      if (/^Unknown (attribute|relation)/i.test(err.message)) {
        return "Unknown name";
      }
      return "Couldn’t run query";
    case "validation_error":
      return "Invalid query";
    case "not_found":
      return "Not found";
    default:
      return fallback;
  }
}

export async function listDatasets(): Promise<DatasetSummary[]> {
  const data = await handle<{ datasets: DatasetSummary[] }>(
    await apiFetch(`${API_BASE}/datasets`, { cache: "no-store" }),
  );
  return data.datasets;
}

export async function getDataset(id: string): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await apiFetch(`${API_BASE}/datasets/${id}`, { cache: "no-store" }),
  );
}

export async function getSharedDataset(token: string): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await apiFetch(`${API_BASE}/datasets/share/${encodeURIComponent(token)}`),
  );
}

export async function copySharedDataset(token: string): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await apiFetch(
      `${API_BASE}/datasets/share/${encodeURIComponent(token)}/copy`,
      { method: "POST" },
    ),
  );
}

export function shareUrl(token: string): string {
  if (typeof window === "undefined") return `/calc?share=${encodeURIComponent(token)}`;
  const url = new URL(window.location.origin + "/calc");
  url.searchParams.set("share", token);
  return url.toString();
}

export async function renameDataset(
  id: string,
  name: string,
): Promise<DatasetDetail> {
  return handle<DatasetDetail>(
    await apiFetch(`${API_BASE}/datasets/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  );
}

export async function deleteDataset(id: string): Promise<void> {
  await handle<{ ok: boolean }>(
    await apiFetch(`${API_BASE}/datasets/${id}`, { method: "DELETE" }),
  );
}

export async function getRelation(
  datasetId: string,
  relationName: string,
): Promise<RelationData> {
  return handle<RelationData>(
    await apiFetch(
      `${API_BASE}/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}`,
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
    await apiFetch(
      `${API_BASE}/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}`,
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
    await apiFetch(
      `${API_BASE}/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}`,
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
    await apiFetch(`${API_BASE}/datasets/${datasetId}/relations`, {
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
    await apiFetch(`${API_BASE}/datasets/${datasetId}/upload`, {
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
    await apiFetch(
      `${API_BASE}/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/columns/${encodeURIComponent(columnName)}`,
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
    await apiFetch(
      `${API_BASE}/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/columns/${encodeURIComponent(columnName)}`,
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
    await apiFetch(
      `${API_BASE}/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/columns`,
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
    await apiFetch(
      `${API_BASE}/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/rows`,
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
    await apiFetch(
      `${API_BASE}/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/rows/${rowIndex}`,
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
    await apiFetch(
      `${API_BASE}/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/rows/${rowIndex}`,
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
    await apiFetch(
      `${API_BASE}/datasets/${datasetId}/relations/${encodeURIComponent(relationName)}/rows`,
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
    await apiFetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function formatQuery(input: {
  language: QueryLanguage;
  query: string;
  style?: "pretty" | "dense";
}): Promise<string> {
  const data = await handle<{ formatted: string }>(
    await apiFetch(`${API_BASE}/format`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        language: input.language,
        query: input.query,
        style: input.style ?? "pretty",
      }),
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
    await apiFetch(`${API_BASE}/datasets/upload`, {
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
    await apiFetch(`${API_BASE}/datasets/build`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function previewGroupText(text: string): Promise<DatasetDetail[]> {
  const data = await handle<{ groups: DatasetDetail[] }>(
    await apiFetch(`${API_BASE}/datasets/group/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),
  );
  return data.groups;
}

export async function installGroupText(text: string): Promise<DatasetDetail[]> {
  const data = await handle<{ groups: DatasetDetail[] }>(
    await apiFetch(`${API_BASE}/datasets/group/install`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),
  );
  return data.groups;
}

export async function exportDatasetText(
  datasetId: string,
): Promise<{ text: string; filename: string | null }> {
  return handle<{ text: string; filename: string | null }>(
    await apiFetch(`${API_BASE}/datasets/${datasetId}/export`, {
      cache: "no-store",
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
