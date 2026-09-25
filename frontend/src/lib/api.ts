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
      message = body?.detail?.message ?? body?.detail ?? message;
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
