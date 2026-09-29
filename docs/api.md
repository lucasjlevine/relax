# API reference

Base URL: `http://localhost:8000/api` (Silk: `/relax-api`)

## `GET /api/health`

```json
{ "status": "ok" }
```

## `GET /api/datasets`

List available dataset groups (built-in + uploaded/built).

Built-in groups: `basics`, `joins`, `setops`, `aggregates`, `library`.

```json
{
  "datasets": [
    {
      "id": "basics",
      "name": "Basics",
      "description": "Single-table practice for selection, projection, and renaming."
    }
  ]
}
```

## `GET /api/datasets/{id}`

Schema and relation metadata for one group.

```json
{
  "id": "basics",
  "name": "Basics",
  "description": "...",
  "relations": [
    {
      "name": "Employee",
      "columns": [
        { "name": "eid", "type": "number" },
        { "name": "name", "type": "string" }
      ],
      "rowCount": 5
    }
  ],
  "exampleRelAlg": "π_{name}(\\n  σ_{dept = 'Engineering'}(Employee)\\n)",
  "exampleSql": "SELECT name\\nFROM Employee\\nWHERE dept = 'Engineering'"
}
```

## Dataset ownership & persistence

User-created datasets (upload, build, Group Editor install, and forks of built-ins) are stored on the server as JSON under `data/user_datasets/`.

- **Owner cookie:** `relax_owner` (HttpOnly). Set automatically on first API request. No accounts.
- **List:** `GET /api/datasets` returns built-ins plus datasets owned by the cookie. Others’ datasets are never listed.
- **Access by id:** Knowing an unguessable `ds_…` id is enough to `GET` / query it (security = obscurity + list filtering).
- **Fork on edit:** Mutating a built-in (`PATCH`, row edits, …) creates a personal copy (`forkedFrom`) and returns the new id. Built-in templates on disk stay unchanged.
- **Share:** Each owned dataset has a `shareToken`.  
  - `GET /api/datasets/share/{token}` — preview  
  - `POST /api/datasets/share/{token}/copy` — clone into the caller’s library  

Browser clients must send cookies (`credentials: "include"`).

## Dataset management

| Method | Path | Purpose |
|--------|------|---------|
| `PATCH` | `/api/datasets/{id}` | Rename dataset (`{ "name": "..." }`). Built-ins fork. |
| `DELETE` | `/api/datasets/{id}` | Delete dataset (built-in: hide for this process; user: remove from disk) |
| `POST` | `/api/datasets/{id}/upload` | Add CSV as a new relation in this dataset |
| `POST` | `/api/datasets/{id}/relations` | Add relation (`relationName`, `columns`, `rows`) |
| `GET` | `/api/datasets/{id}/relations/{name}` | Relation columns + rows |
| `PATCH` | `/api/datasets/{id}/relations/{name}` | Rename relation (`{ "name": "..." }`) |
| `DELETE` | `/api/datasets/{id}/relations/{name}` | Delete relation |
| `PATCH` | `/api/datasets/{id}/relations/{name}/columns/{col}` | Rename and/or change type (`{ "name"?, "type"? }`). Number conversion strips `$` / commas; bad cells become null. |
| `POST` | `/api/datasets/{id}/relations/{name}/columns` | Add column (`{ "name", "type"?, "default"? }`) |
| `DELETE` | `/api/datasets/{id}/relations/{name}/columns/{col}` | Delete column |
| `POST` | `/api/datasets/{id}/relations/{name}/rows` | Add row (`{ "values": [...] }`) |
| `PUT` | `/api/datasets/{id}/relations/{name}/rows` | Replace all rows |
| `PUT` | `/api/datasets/{id}/relations/{name}/rows/{i}` | Update row |
| `DELETE` | `/api/datasets/{id}/relations/{name}/rows/{i}` | Delete row |
| `GET` | `/api/datasets/share/{token}` | Preview a shared user dataset |
| `POST` | `/api/datasets/share/{token}/copy` | Copy a shared dataset into the caller’s library |

## `POST /api/datasets/upload`

Upload `.csv` / `.db` / `.sqlite` (multipart form).

## `POST /api/datasets/build`

Create a dataset from column/row JSON.

## Group Editor (RelaX `local_groups`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/datasets/group/preview` | Parse group text without installing (`{ "text": "…" }`) |
| `POST` | `/api/datasets/group/install` | Parse and install all groups from text |
| `GET` | `/api/datasets/{id}/export` | Export dataset as RelaX-compatible text (`{ text, filename }`) |
| `GET` | `/api/datasets/{id}/export.txt` | Same export as a downloadable plain-text file |

See [group-editor.md](./group-editor.md) for the text format.

## `POST /api/query`

Execute RelAlg or SQL against a dataset.

### Request

```json
{
  "datasetId": "basics",
  "language": "relalg",
  "query": "π_{name}(σ_{salary > 80000}(Employee))",
  "limit": 100,
  "offset": 0
}
```

`language`: `"relalg"` | `"sql"`

RelAlg may contain multiple statements separated by `;`. The response includes a `results` array (one block per statement). Top-level `columns` / `rows` / `tree` mirror the **last** statement for compatibility.

When a query implies a different type, the server converts and **persists** that column’s type on the dataset, and lists the change in `typeChanges` / `warnings`. If the dataset was a built-in, it is forked first (`datasetId` may change).

Triggers include:

- Comparisons to typed literals (e.g. string `Movie.year < 1960` → number)
- Numeric aggregates `sum` / `avg` / `min` / `max` (e.g. `avg(Ratings.rev_stars)` → number)
- Numeric helpers (`abs`, `round`, `floor`, `ceil`, `add`/`sub`/`mul`/`div`/`mod`) and arithmetic (`+`, `-`, `*`, `/`, `%`)
- Date helpers (`date`, `adddate`, `subdate`)

### Success response

```json
{
  "columns": [{ "name": "name", "type": "string" }],
  "rows": [["Ana"], ["Cara"]],
  "rowCount": 2,
  "executionMs": 1.2,
  "tree": {
    "id": "1",
    "label": "π name",
    "operator": "projection",
    "children": []
  },
  "warnings": [],
  "results": [
    {
      "index": 0,
      "label": null,
      "columns": [{ "name": "name", "type": "string" }],
      "rows": [["Ana"], ["Cara"]],
      "rowCount": 2,
      "executionMs": 1.2,
      "tree": { "id": "1", "label": "π name", "operator": "projection", "children": [] },
      "warnings": []
    }
  ],
  "datasetId": "basics",
  "typeChanges": []
}
```

## `POST /api/format`

Pretty-print RelAlg (subscript notation) or SQL.

Body: `{ "query", "language", "style"? }` where `style` is `pretty` (default: indented, fully parenthesized) or `dense` (single-line RelAlg, omit implied parentheses; compact SQL).
