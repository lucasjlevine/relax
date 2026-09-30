# Architecture

## Overview

Relational Playground is a monorepo teaching tool for Relational Algebra (RelAlg) and SQL.
Inspired by [RelaX](https://dbis-uibk.github.io/relax/landing); separate project, not affiliated.

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
3. **Educational, not production DB** — queries with row limits; user datasets persist as JSON under cookie ownership (no accounts).
4. **RelAlg + SQL only** — BagAlg / TRC are out of scope unless explicitly requested. Group Editor is in scope and RelaX format-compatible.

## Frontend

- App Router pages: `/` (landing + guide), `/calc` (calculator)
- Resizable dataset sidebar (Manage / Group auto-expand)
- Shadcn primitives + CodeMirror editor (query + Group Editor)
- Calls `NEXT_PUBLIC_API_URL` (API root including prefix, e.g. `http://localhost:8000/api` or Silk `/api`) for datasets, mutations, and query execution

## Backend

| Package | Role |
|---------|------|
| `app.datasets` | Built-in `local_groups`, disk-backed user datasets (`data/user_datasets`), cookie ownership, fork-on-edit, share tokens |
| `app.parsers.relalg` | Lark grammar → AST + formatter |
| `app.parsers.sql` | sqlglot validation |
| `app.engine` | Compile AST / SQL to DuckDB, build operator tree |

## Data flow (query)

1. Client posts `{ datasetId, language, query }`
2. Loader opens in-memory DuckDB and registers group tables
3. Parser builds AST (RelAlg) or validates SQL
4. Engine compiles and executes with limit/offset
5. Response includes columns, rows, timing, operator tree
