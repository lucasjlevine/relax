# Deploying relax on UVM Silk

This app targets [UVM Silk](https://silk.uvm.edu/) hosting: Next.js (Node) for the UI and FastAPI for `/api/*`, both under **NGINX Unit** via `.silk.ini`.

Silk does **not** allow web apps to bind their own ports or run as listening `systemctl` services. Use Unit (`silk app … load`). User systemd is only relevant off Silk; see `deploy/silk/systemd/` for a non-Silk example.

## Architecture on Silk

| Piece | Silk app | URI | How it runs |
|-------|----------|-----|-------------|
| FastAPI | `[app: api]` | `/api*` | WSGI via `a2wsgi` (`backend/wsgi.py`) |
| Next.js | `[app: web]` | `/*` | Standalone `server.js` (Node 22) |

The browser talks to the same host: `NEXT_PUBLIC_API_URL` is empty at build time, so the UI calls `/api/...` on `https://NETID.w3.uvm.edu`.

```
Browser → https://NETID.w3.uvm.edu/calc
                → Unit [app: web]  → Next.js
Browser → https://NETID.w3.uvm.edu/api/...
                → Unit [app: api]  → FastAPI (WSGI)
```

Official refs:

- [Node.js on Silk](https://silk.uvm.edu/manual/nodejs/)
- [Python on Silk](https://silk.uvm.edu/manual/python/)
- [`.silk.ini` options](https://silk.uvm.edu/manual/config-options/)
- [Hosting overview](https://silk.uvm.edu/hosting-questions/)

## Prerequisites

- Silk account (`ssh NETID@w3.uvm.edu`) — request via [SAA](https://silk.uvm.edu/) if needed
- Local: Node.js 22+ (or 20+), Python 3.12+, `rsync`, SSH access to Silk
- This branch: `deploy/silk`

## One-time Silk setup

```bash
ssh NETID@w3.uvm.edu

# Python 3.12 venv for the API (path must match .silk.ini venv-path)
mkdir -p ~/venvs
python3 -m venv ~/venvs/relax

# Site root is usually ~/www-root — confirm with `silk account info` / ls
mkdir -p ~/www-root/public ~/www-root/web ~/www-root/api
```

Copy and edit the Unit config:

```bash
# From your laptop (after cloning this branch)
scp deploy/silk/.silk.ini NETID@w3.uvm.edu:~/www-root/.silk.ini
```

On Silk, edit `~/www-root/.silk.ini`:

1. Set `venv-path` to the absolute path of `~/venvs/relax` (resolve with `readlink -f ~/venvs/relax`).
2. Set `env.CORS_ORIGINS` to your hostname, e.g. `["https://NETID.w3.uvm.edu"]`.
3. Keep `[app: api]` URI `/api*` and `[app: web]` URI `/*`.

## Build and sync (laptop)

From the repo root on `deploy/silk`:

```bash
chmod +x deploy/silk/*.sh
./deploy/silk/sync-to-silk.sh --build NETID
```

Or step by step:

```bash
./deploy/silk/build-web.sh      # → deploy/silk/dist/web
./deploy/silk/prepare-api.sh    # → deploy/silk/dist/api
./deploy/silk/sync-to-silk.sh NETID
```

Optional env when building the UI against a different API origin:

```bash
NEXT_PUBLIC_API_URL=https://other.example.edu ./deploy/silk/build-web.sh
```

## Install API deps on Silk (after each sync that changes Python deps)

```bash
ssh NETID@w3.uvm.edu
~/venvs/relax/bin/pip install ~/www-root/api
chmod u+x ~/www-root/api/wsgi.py ~/www-root/web/server.js
```

## Load / reload apps

```bash
ssh NETID@w3.uvm.edu
silk update
silk app NETID.w3.uvm.edu/api load
silk app NETID.w3.uvm.edu load
```

If you only changed one side, reload that app’s URI. Logs:

- App server log paths are documented on the [Node](https://silk.uvm.edu/manual/nodejs/) / [Python](https://silk.uvm.edu/manual/python/) pages (Unit `unit.log` under the account).

Smoke check:

- `https://NETID.w3.uvm.edu/api/health` → `{"status":"ok"}`
- `https://NETID.w3.uvm.edu/calc` → calculator UI

## Writable data

The API writes under `api/data/uploads` and `api/data/user_datasets`. Ensure those directories exist and are writable by your NetID after sync (`prepare-api.sh` creates them; rsync excludes local scratch JSON).

## Why not `systemctl --user` on Silk?

Silk’s hosting overview states that Python/Node web apps must be launched through the app server and **cannot** be started as services that listen for network requests. Unit owns the socket; your `startup-script` is loaded by Unit.

If you later run the stack on a VM or laptop with user systemd, see `deploy/silk/systemd/relax-api.service.example`.

## Checklist

- [ ] `.silk.ini` on site root with real `venv-path` and `CORS_ORIGINS`
- [ ] `~/venvs/relax` created; `pip install` of `~/www-root/api` succeeds
- [ ] `wsgi.py` and `server.js` are executable (`chmod u+x`)
- [ ] `silk app …/api load` and `silk app … load` succeed
- [ ] `/api/health` and `/calc` work over HTTPS
