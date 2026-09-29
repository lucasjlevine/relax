# Deploying relax on UVM Silk

NetID **jlhorton**, repo at `~/www-root/relax`.

## URL layout (non-overlapping)

| App | Unit `uri` | Public URL |
|-----|------------|------------|
| Next UI | `/relax` and `/relax/*` | https://jlhorton.w3.uvm.edu/relax/ |
| FastAPI | `/relax-api*` | https://jlhorton.w3.uvm.edu/relax-api/health |

Do **not** use `uri = /relax*` for the UI — that also matches `/relax-api`.

Local/Docker stay on `/api` and no `basePath`. Silk sets `API_ROOT_PATH=/relax-api` and builds the UI with `SILK_DEPLOY=1` (`basePath=/relax`) and `NEXT_PUBLIC_API_URL=/relax-api`.

## Install

```bash
ssh jlhorton@w3.uvm.edu
cd ~/www-root/relax
git pull
chmod +x deploy/silk/*.sh
./deploy/silk/install-on-silk.sh
```

Manual load:

```bash
cp deploy/silk/.silk.ini ~/www-root/.silk.ini
# fix venv-path if needed
silk site jlhorton.w3.uvm.edu update
silk app jlhorton.w3.uvm.edu/relax-api load
silk app jlhorton.w3.uvm.edu/relax load
```

## Smoke

```bash
curl -sS -D - --compressed "https://jlhorton.w3.uvm.edu/relax-api/health"
# Body: {"status":"ok","via":"wsgi"}
# Header: X-Relax-Backend: wsgi-health

open "https://jlhorton.w3.uvm.edu/relax/calc/"
```

## Stale catch-all `/*` Node app

If something still serves a Next 404 on `/relax-api/...`, unload the old root app (`silk app help` for unload/delete) or ask [SAA](mailto:saa@uvm.edu). Confirm `~/www-root/.silk.ini` has no `uri = /*` Node section.
