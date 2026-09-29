# Silk packaging

Scripts and Unit config for hosting relax on [UVM Silk](https://silk.uvm.edu/).

**Full guide:** [docs/silk-deploy.md](../../docs/silk-deploy.md)

| Path | Purpose |
|------|---------|
| `.silk.ini` | NGINX Unit app definitions (`/api*` + `/*`) |
| `build-web.sh` | Next.js standalone → `dist/web` |
| `prepare-api.sh` | FastAPI tree → `dist/api` |
| `sync-to-silk.sh` | rsync to `NETID@w3.uvm.edu` |
| `systemd/` | Example user unit for **non-Silk** hosts only |

Quick path:

```bash
./deploy/silk/sync-to-silk.sh --build NETID
```
