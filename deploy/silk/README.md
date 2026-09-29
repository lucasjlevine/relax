# Silk packaging (jlhorton)

Repo on Silk: **`~/www-root/relax`**. Unit config must be at **`~/www-root/.silk.ini`**.

**Full guide:** [docs/silk-deploy.md](../../docs/silk-deploy.md)

## Quick answer: where is the frontend build?

`deploy/silk/dist/` is **gitignored**. Create it on Silk:

```bash
cd ~/www-root/relax
./deploy/silk/build-web.sh
# → deploy/silk/dist/web/server.js
```

Or run everything:

```bash
./deploy/silk/install-on-silk.sh
```

| Path | Purpose |
|------|---------|
| `.silk.ini` | Template — copy to `~/www-root/.silk.ini` |
| `build-web.sh` | Next standalone → `dist/web` |
| `install-on-silk.sh` | Build + venv + install ini + `silk app load` |
| `prepare-api.sh` | Optional staged API tree (not needed if Unit uses `relax/backend`) |
| `sync-to-silk.sh` | Laptop rsync to flat `www-root/{web,api}` (alternate layout) |
