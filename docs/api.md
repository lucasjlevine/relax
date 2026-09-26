# API reference

Base URL: `http://localhost:8000`

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

## Dataset management

| Method | Path | Purpose |
|--------|------|---------|
| `PATCH` | `/api/datasets/{id}` | Rename dataset (`{ "name": "..." }`) |
| `DELETE` | `/api/datasets/{id}` | Delete dataset |
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

### Success response

```json
{
  "columns": [{ "name": "name", "type": "VARCHAR" }],
  "rows": [["Ana"], ["Cara"]],
  "rowCount": 2,
  "executionMs": 1.2,
  "tree": {
    "id": "1",
    "label": "π name",
    "operator": "projection",
    "children": []
  },
  "warnings": []
}
```

## `POST /api/format`

Pretty-print RelAlg (subscript notation) or SQL.
