# API reference

Base URL: `http://localhost:8000`

## `GET /api/health`

```json
{ "status": "ok" }
```

## `GET /api/datasets`

List available dataset groups.

```json
{
  "datasets": [
    {
      "id": "misc-rst",
      "name": "R, S, T",
      "description": "Small relations for join practice"
    }
  ]
}
```

## `GET /api/datasets/{id}`

Schema and relation metadata for one group.

```json
{
  "id": "misc-rst",
  "name": "R, S, T",
  "description": "...",
  "relations": [
    {
      "name": "R",
      "columns": [
        { "name": "a", "type": "number" },
        { "name": "b", "type": "string" },
        { "name": "c", "type": "string" }
      ],
      "rowCount": 5
    }
  ]
}
```

## `POST /api/query`

Execute RelAlg or SQL against a dataset.

### Request

```json
{
  "datasetId": "misc-rst",
  "language": "relalg",
  "query": "pi a (sigma a > 1 (R))",
  "limit": 100,
  "offset": 0
}
```

`language`: `"relalg"` | `"sql"`

### Success response

```json
{
  "columns": [
    { "name": "a", "type": "number" }
  ],
  "rows": [[2], [4]],
  "rowCount": 2,
  "executionMs": 1.2,
  "tree": {
    "id": "1",
    "label": "π a",
    "operator": "projection",
    "children": [
      {
        "id": "2",
        "label": "σ a > 1",
        "operator": "selection",
        "children": [
          { "id": "3", "label": "R", "operator": "relation", "children": [] }
        ]
      }
    ]
  },
  "warnings": []
}
```

## `POST /api/format`

Pretty-print a query. RelAlg is rewritten to classical subscript notation.

### Request

```json
{ "language": "relalg", "query": "pi a (sigma a > 1 (R))" }
```

### Response

```json
{ "formatted": "π_{a}(σ_{a > 1}(R))" }
```

## `POST /api/datasets/upload`

Multipart form fields:

| Field | Description |
|-------|-------------|
| `file` | `.csv`, `.db`, `.sqlite`, or `.sqlite3` (max 5 MB) |
| `relationName` | Optional table name for CSV |
| `hasHeader` | `true`/`false` — treat first data row as header (default true) |
| `skipRows` | Integer rows to skip from the top (default 0) |
| `delimiter` | CSV delimiter: `,`, `;`, tab, or `\|` (default `,`) |

## `POST /api/datasets/build`

Build a relation from JSON:

```json
{
  "name": "Custom",
  "relationName": "R",
  "columns": [{ "name": "a", "type": "number" }],
  "rows": [[1], [2]]
}
```
