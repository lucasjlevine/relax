# Architecture

## Overview

relax is a monorepo teaching tool for Relational Algebra (RelAlg) and SQL.

```
Browser (Next.js)
    │  REST JSON
    ▼
FastAPI
    ├── Dataset loader  → DuckDB relations
    ├── RelAlg (Lark)   → AST → DuckDB SQL + operator tree
    └── SQL (sqlglot)   → validated SELECT → DuckDB
```

## Design principles

1. **RelaX-compatible RelAlg syntax** — plaintext keywords (`sigma`, `pi`, `join`) and unicode symbols (`σ`, `π`, `⋈`), including classical subscripts.
2. **DuckDB as execution engine** — fast columnar queries on educational datasets.
3. **Educational, not production DB** — queries with row limits; in-memory mutable catalog for teaching edits.
4. **RelAlg + SQL only** — BagAlg / TRC / GE are out of scope unless explicitly requested.

## Frontend

- App Router pages: `/` (landing + guide), `/calc` (calculator)
- Resizable dataset sidebar (Manage auto-expands)
- Shadcn primitives + CodeMirror editor
- Calls `NEXT_PUBLIC_API_URL` for datasets, mutations, and query execution

## Backend

| Package | Role |
|---------|------|
| `app.datasets` | Built-in `local_groups`, `WorkingCatalog` mutations, user uploads |
| `app.parsers.relalg` | Lark grammar → AST + formatter |
| `app.parsers.sql` | sqlglot validation |
| `app.engine` | Compile AST / SQL to DuckDB, build operator tree |

## Data flow (query)

1. Client posts `{ datasetId, language, query }`
2. Loader opens in-memory DuckDB and registers group tables
3. Parser builds AST (RelAlg) or validates SQL
4. Engine compiles and executes with limit/offset
5. Response includes columns, rows, timing, operator tree
