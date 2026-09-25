# relax

A web-based Relational Algebra and SQL learning calculator inspired by [RelaX](https://dbis-uibk.github.io/relax/landing).

Write RelAlg or SQL against example datasets, execute queries, and inspect results plus an operator tree.

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js (App Router), TypeScript, Shadcn UI, CodeMirror 6 |
| Backend | Python 3.12, FastAPI, DuckDB, Lark, sqlglot |

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

App: http://localhost:3000

### Docker Compose

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

## Project layout

```
relax/
├── frontend/     # Next.js calculator UI
├── backend/      # FastAPI + DuckDB engine
├── docs/         # Architecture, syntax, API
└── .cursor/rules/
```

## Documentation

- [Architecture](docs/architecture.md)
- [RelAlg syntax](docs/relalg-syntax.md)
- [API reference](docs/api.md)
- [Development](docs/development.md)

## Scope

**Supported (MVP):** RelAlg core operators and SQL SELECT subset.  
**Not in scope:** BagAlg, TRC, group editor, gist datasets (planned later).

## Example queries

RelAlg:

```text
pi a (sigma a > 1 (R))
R join S
```

SQL:

```sql
SELECT a FROM R WHERE a > 1
SELECT * FROM R NATURAL JOIN S
```
