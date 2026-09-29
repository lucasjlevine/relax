# Deploying relax on UVM Silk

Target: [UVM Silk](https://silk.uvm.edu/) for NetID **jlhorton**, with the git repo at:

```text
~/www-root/relax          ← this repository
~/www-root/.silk.ini      ← Unit config (site root, NOT inside the repo)
~/www-root/public         ← static fallback document-root
~/venvs/relax             ← Python venv for FastAPI deps
```

Silk does **not** allow web apps to bind their own ports. Use NGINX Unit via `.silk.ini` and `silk app … load`.

## Why things were “not found”

1. **`.silk.ini` must live at the site root** (`~/www-root/.silk.ini`). Silk does not read `relax/deploy/silk/.silk.ini` by itself — copy it up one level.
2. **`root` is relative to `~/www-root`**, not to the repo. For this layout that means `relax/backend` and `relax/deploy/silk/dist/web`.
3. **`deploy/silk/dist/web` is not in git.** It is created by `build-web.sh` (Next.js standalone). Until you build, Unit cannot find `server.js`.

## Is there supposed to be a frontend build directory?

Yes. After `./deploy/silk/build-web.sh` (or `install-on-silk.sh`):

```text
deploy/silk/dist/web/          ← gitignored runtime tree for Unit
  server.js                    ← startup-script
  public/
  .next/static/
  …
```

`prepare-api.sh` / `dist/api` are optional when the repo is on Silk — Unit can run Python straight from `relax/backend`. The frontend **must** be built; source `frontend/` is not what Unit runs.

## Architecture

| Piece | Silk app | `root` (under www-root) | URI |
|-------|----------|-------------------------|-----|
| FastAPI | `[app: api]` | `relax/backend` | `/api*` |
| Next.js | `[app: web]` | `relax/deploy/silk/dist/web` | `/*` |

Same-origin: production UI is built with empty `NEXT_PUBLIC_API_URL`, so the browser calls `/api/...` on `https://jlhorton.w3.uvm.edu`.

Official refs: [Node](https://silk.uvm.edu/manual/nodejs/), [Python](https://silk.uvm.edu/manual/python/), [config](https://silk.uvm.edu/manual/config-options/), [overview](https://silk.uvm.edu/hosting-questions/).

## Recommended: build and install on Silk

SSH in, then from the clone:

```bash
ssh jlhorton@w3.uvm.edu
cd ~/www-root/relax
git checkout deploy/silk   # if needed
chmod +x deploy/silk/*.sh
./deploy/silk/install-on-silk.sh
```

That script:

1. Runs `build-web.sh` → `deploy/silk/dist/web`
2. Creates `~/venvs/relax` and `pip install`s `backend/`
3. Copies `.silk.ini` to `~/www-root/.silk.ini` (rewrites `venv-path` to the absolute path)
4. Runs `silk site jlhorton.w3.uvm.edu update` and loads `/api` + `/*`

Manual equivalent:

```bash
cd ~/www-root/relax
./deploy/silk/build-web.sh
python3 -m venv ~/venvs/relax
~/venvs/relax/bin/pip install ~/www-root/relax/backend
chmod u+x backend/wsgi.py deploy/silk/dist/web/server.js
mkdir -p ~/www-root/public backend/data/uploads backend/data/user_datasets
cp deploy/silk/.silk.ini ~/www-root/.silk.ini
# confirm venv-path = output of: readlink -f ~/venvs/relax
silk site jlhorton.w3.uvm.edu update
silk app jlhorton.w3.uvm.edu/api load
silk app jlhorton.w3.uvm.edu load
```

Smoke:

```bash
# Expect JSON + header X-Relax-Backend: wsgi-health (not binary garbage)
curl -sS -D - --compressed "https://jlhorton.w3.uvm.edu/api/health"
```

- Browser: https://jlhorton.w3.uvm.edu/api/health → `{"status":"ok","via":"wsgi"}`
- https://jlhorton.w3.uvm.edu/calc

### Binary / gzip garbage from `/api/...`

That payload starting with mojibake/`0x1f 0x8b` is **gzip**. Usual causes:

1. **Next.js handled `/api/*`** (Python app not loaded or uri mismatch) — response is a compressed Next body.
2. **Double gzip** (Next `compress` + Silk front proxy) — rebuild web after `compress: false`.
3. **curl without decompress** — use `curl --compressed` or check headers with `curl -D -`.

Check which app answered:

```bash
curl -sS -D - -o /dev/null "https://jlhorton.w3.uvm.edu/api/health" | grep -iE 'HTTP/|content-type|content-encoding|x-relax'
```

You want `X-Relax-Backend: wsgi-health` and `content-type: application/json`. If that header is missing, reload:

```bash
cp ~/www-root/relax/deploy/silk/.silk.ini ~/www-root/.silk.ini
silk site jlhorton.w3.uvm.edu update
silk app jlhorton.w3.uvm.edu/api load
silk app jlhorton.w3.uvm.edu load
```

## Laptop → Silk sync (optional)

If you build on a laptop instead of on Silk:

```bash
./deploy/silk/build-web.sh
# rsync dist/web into ~/www-root/relax/deploy/silk/dist/web on Silk
# keep backend in the git clone; only the web dist must be present
```

`sync-to-silk.sh` still targets flat `~/www-root/{web,api}` — that layout is **not** what jlhorton’s repo-under-www-root setup uses. Prefer `install-on-silk.sh` on the server.

## After code changes

| Change | Action |
|--------|--------|
| Frontend | `./deploy/silk/build-web.sh` then `silk app jlhorton.w3.uvm.edu load` |
| Backend Python | `~/venvs/relax/bin/pip install ~/www-root/relax/backend` then `silk app jlhorton.w3.uvm.edu/api load` |
| `.silk.ini` | Edit `~/www-root/.silk.ini`, `silk site jlhorton.w3.uvm.edu update`, reload apps |

## Checklist

- [ ] Repo at `~/www-root/relax`
- [ ] `~/www-root/.silk.ini` present (copied from `deploy/silk/.silk.ini`)
- [ ] `deploy/silk/dist/web/server.js` exists (built)
- [ ] `~/venvs/relax` installed; `venv-path` matches `readlink -f ~/venvs/relax`
- [ ] `backend/wsgi.py` and `dist/web/server.js` are executable
- [ ] `silk app jlhorton.w3.uvm.edu/api load` and `silk app jlhorton.w3.uvm.edu load` succeed
