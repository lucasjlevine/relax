# Deploying relax on UVM Silk

NetID **jlhorton**, repo at `~/www-root/relax`.

## Why not Next as a Unit app?

A Node app with `uri = /*` receives **all** paths, including `/api/...`, so FastAPI never runs (Next 404 or gzip garbage). Silk multi-app routing did not prefer `/api*` over `/*` in practice.

**Solution:** static Next export as the site `document-root`, and a **single** Python Unit app for `/api*`.

```text
~/www-root/.silk.ini
~/www-root/relax/                     ← git clone
~/www-root/relax/deploy/silk/dist/web ← static UI (gitignored, from build-web.sh)
~/www-root/relax/backend/             ← FastAPI + wsgi.py
~/venvs/relax                         ← Python venv
```

```
Browser → /calc, /guide, /     → static files (document-root)
Browser → /api/...             → Unit [app: api] → wsgi.py → FastAPI
```

## One-shot install on Silk

```bash
ssh jlhorton@w3.uvm.edu
cd ~/www-root/relax
git pull
chmod +x deploy/silk/*.sh
./deploy/silk/install-on-silk.sh
```

That builds the static UI, installs the venv, copies `.silk.ini` to `~/www-root/.silk.ini`, and runs:

```bash
silk site jlhorton.w3.uvm.edu update
silk app jlhorton.w3.uvm.edu/api load
```

## Smoke checks

```bash
curl -sS -D - --compressed "https://jlhorton.w3.uvm.edu/api/health"
# Body: {"status":"ok","via":"wsgi"}
# Header: X-Relax-Backend: wsgi-health
```

- https://jlhorton.w3.uvm.edu/calc
- https://jlhorton.w3.uvm.edu/

## After code changes

| Change | Action |
|--------|--------|
| Frontend | `./deploy/silk/build-web.sh` (no app reload needed for static files; hard-refresh browser) |
| Backend | `~/venvs/relax/bin/pip install ~/www-root/relax/backend` then `silk app jlhorton.w3.uvm.edu/api load` |
| `.silk.ini` | Edit `~/www-root/.silk.ini`, `silk site jlhorton.w3.uvm.edu update`, reload `/api` |

## Stale Node app

If `/api/health` still shows a **Next** 404 after switching, an old Node Unit app may still be registered. Confirm `~/www-root/.silk.ini` has **no** `[app: web]` / `type = nodejs` section, run `silk site jlhorton.w3.uvm.edu update`, reload the API, and check `/var/opt/nginx-unit/.../unit.log` (see [Python manual](https://silk.uvm.edu/manual/python/)). Contact [SAA](https://silk.uvm.edu/) if a stale app will not clear.

## Local / Docker

Unchanged: Next still uses `output: "standalone"` unless `SILK_STATIC=1` (set only by `build-web.sh` for Silk).
