# Deploying Relational Playground on UVM Silk

NetID **jlhorton**, repo at `~/www-root/relax`.

## Architecture

| Piece | How it runs |
|-------|-------------|
| Next.js UI | Silk Unit Node app (`uri = /*`) |
| FastAPI | `systemd --user` on `127.0.0.1:8000` |
| Browser `/api/*` | Next **rewrites** → localhost uvicorn |

No Python Unit / WSGI. No `/relax-api` path split.

```
Browser → https://jlhorton.w3.uvm.edu/calc
                → Unit [Node] → Next.js
Browser → https://jlhorton.w3.uvm.edu/api/...
                → Unit [Node] → Next rewrite → 127.0.0.1:8000
```

## Install

```bash
cd ~/www-root/relax
git pull
chmod +x deploy/silk/*.sh
./deploy/silk/install-on-silk.sh
```

Keep the API alive after SSH logout (once):

```bash
loginctl enable-linger jlhorton
```

## Day-to-day

| Change | Command |
|--------|---------|
| Backend code | `~/venvs/relax/bin/pip install ~/www-root/relax/backend && systemctl --user restart relax-api` |
| Frontend | `./deploy/silk/build-web.sh && silk app jlhorton.w3.uvm.edu load` |
| API logs | `journalctl --user -u relax-api -f` |
| API status | `systemctl --user status relax-api` |

## Smoke

```bash
curl -sS http://127.0.0.1:8000/api/health
curl -sS -D - --compressed "https://jlhorton.w3.uvm.edu/api/health"
open "https://jlhorton.w3.uvm.edu/calc"
```
