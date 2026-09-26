# relax

A web-based **Relational Algebra** and **SQL** learning calculator inspired by [RelaX](https://dbis-uibk.github.io/relax/landing).

Write RelAlg or SQL against teaching datasets, execute instantly, inspect a result table and operator tree, manage or upload data, and export CSV.

## Quickstart

### Prerequisites

- Node.js 20+
- Python 3.12+
- (Optional) Docker

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000 · Calculator: http://localhost:3000/calc · Guide: http://localhost:3000/guide

### Docker Compose

```bash
docker compose up --build
```

## What matters most

| Topic | Short version |
|-------|----------------|
| **Modes** | RelAlg and SQL share one execute → results → tree flow |
| **Notation** | Unicode subscripts (`π_{…}`) *and* plaintext (`pi …`); **Format** rewrites to classical style |
| **Helpers** | SQL-like functions in expressions: `rownum()`, `length()`, `date()`, `CASE WHEN …`, … — see [docs/functions.md](docs/functions.md) or **Functions** in the calculator |
| **Datasets** | Five built-ins: Basics, Joins, SetOps, Aggregates, Library — plus CSV/SQLite upload and in-app builder |
| **Manage** | Rename/delete datasets, relations, and columns; edit rows; add another relation (or CSV) into the same dataset; drag the left panel wider |
| **Export** | Download the current result as CSV |
| **Persistence** | Last dataset + query restored on reload; **History** reuses past executions |
| **Scope** | RelAlg + SQL only — not BagAlg / TRC / GE |

Full walkthrough: **[docs/user-guide.md](docs/user-guide.md)**

## Example queries

RelAlg (classical subscript):

```text
π_{name}(
  σ_{dept = 'Engineering'}(Employee)
)
```

RelAlg (prefix):

```text
pi name (sigma dept = 'Engineering' (Employee))
```

SQL:

```sql
SELECT name
FROM Employee
WHERE dept = 'Engineering'
```

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js (App Router), TypeScript, Shadcn UI, CodeMirror 6 |
| Backend | Python 3.12, FastAPI, DuckDB, Lark, sqlglot |

## Project layout

```
relax/
├── frontend/     # Next.js UI (landing, /calc, /guide)
├── backend/      # FastAPI + DuckDB engine
├── docs/         # User guide, syntax, API, architecture
└── .cursor/rules/
```

## Documentation

- [User guide](docs/user-guide.md) — features & UX tips (also in-app at `/guide`)
- [Helper functions](docs/functions.md) — `rownum()`, dates, strings, …
- [RelAlg syntax](docs/relalg-syntax.md)
- [API reference](docs/api.md)
- [Architecture](docs/architecture.md)
- [Development](docs/development.md)
