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

1. **RelaX-compatible RelAlg syntax** — plaintext keywords (`sigma`, `pi`, `join`) and unicode symbols (`σ`, `π`, `⋈`).
2. **DuckDB as execution engine** — fast columnar queries on educational datasets.
3. **Educational, not production DB** — read-only queries, row limits, timeouts.
4. **Incremental features** — core ops first; outer joins / γ / τ / gist later.

## Frontend

- App Router pages: `/` (landing), `/calc` (calculator)
- Shadcn for accessible primitives
- CodeMirror for RelAlg/SQL editing
- Calls `NEXT_PUBLIC_API_URL` for datasets and query execution

## Backend

| Package | Role |
|---------|------|
| `app.datasets` | Parse RelaX `group:` files, register tables |
| `app.parsers.relalg` | Lark grammar → AST |
| `app.parsers.sql` | sqlglot validation |
| `app.engine` | Compile AST / SQL to DuckDB, build tree |

## Data flow (query)

1. Client posts `{ datasetId, language, query }`
2. Loader opens in-memory DuckDB and registers group tables
3. Parser builds AST (RelAlg) or validates SQL
4. Engine compiles and executes with limit/offset
5. Response includes columns, rows, timing, operator tree
