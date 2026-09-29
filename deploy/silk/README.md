# Silk (jlhorton)

| URL | Mechanism |
|-----|-----------|
| `/relax/` | Static Next export in `~/www-root/public/relax/` |
| `/relax-api/` | Python Unit app only |

**Do not** run Next under Unit — proxy errors / stuck `prototype` process.

```bash
FORCE=1 ./deploy/silk/kill-stale-apps.sh
./deploy/silk/install-on-silk.sh
```

Details: [docs/silk-deploy.md](../../docs/silk-deploy.md)
