# Deploying relax on UVM Silk

NetID **jlhorton**, repo at `~/www-root/relax`.

## Why no Node Unit app?

NGINX Unit’s Node adapter is **not** a full Node `http.ServerResponse`. Next.js App Router often dies with proxy errors (application process never stays up — you only see a Unit `prototype`).

So on Silk:

| Piece | How |
|-------|-----|
| UI | **Static export** → `~/www-root/public/relax/` (URL `/relax/`) |
| API | **Python Unit** → `uri = /relax-api*` |

## Install

```bash
cd ~/www-root/relax
git pull
FORCE=1 ./deploy/silk/kill-stale-apps.sh   # clear old Node workers
./deploy/silk/install-on-silk.sh
```

Confirm `ps` shows **no** `nodejs` / `server.js` Unit apps — only `relax_api`:

```bash
ps -u "$USER" -o pid,args | grep -E 'unit:|node|wsgi' | grep -v grep
```

## Smoke

```bash
curl -sS -D - --compressed "https://jlhorton.w3.uvm.edu/relax-api/health"
# expect X-Relax-Backend: wsgi-health

# UI
curl -sS -o /dev/null -w "%{http_code}\n" "https://jlhorton.w3.uvm.edu/relax/"
# expect 200
```

## Proxy errors on API

1. Enable WSGI debug log in `~/www-root/.silk.ini` under `[app: api]`:
   ```ini
   env.RELAX_WSGI_DEBUG = /users/j/l/jlhorton/relax-wsgi.log
   ```
   Then `silk app jlhorton.w3.uvm.edu/relax-api load` and retry; `cat ~/relax-wsgi.log`.

2. Unit logs:
   ```bash
   tail -100 /var/opt/nginx-unit/*/unit.log
   ```

3. DuckDB must import in the venv (native wheel):
   ```bash
   ~/venvs/relax/bin/python -c "import duckdb; print(duckdb.__version__)"
   ```
