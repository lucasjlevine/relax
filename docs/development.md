# Development

## One-command local stack

From the repo root:

```bash
./start.sh          # macOS / Linux
.\start.ps1         # Windows PowerShell
```

Use `--setup` / `-Setup` to install dependencies without starting servers, or `--docker` / `-Docker` to use Compose.

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
NEXT_PUBLIC_API_URL=http://localhost:8000/api npm run dev
```

## Feature branches

Prefer small branches such as `feat/relalg-core`, `feat/sql-mode`, `feat/calc-ui`.
Merge when tests and a manual calculator smoke check pass.

## Silk deployment

Branch `deploy/silk` packages the stack for [UVM Silk](https://silk.uvm.edu/) (NGINX Unit, not port-binding systemd). See [silk-deploy.md](./silk-deploy.md) and scripts under `deploy/silk/`.

## Docs for contributors

Start with [user-guide.md](./user-guide.md) for product behavior, then [architecture.md](./architecture.md).
