# Development

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
pytest
```

## Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## Feature branches

Prefer small branches such as `feat/relalg-core`, `feat/sql-mode`, `feat/calc-ui`.
Merge when tests and a manual calculator smoke check pass.
