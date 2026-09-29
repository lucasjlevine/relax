# Silk packaging (jlhorton)

| URL | App |
|-----|-----|
| `/relax/` | Next (Unit nodejs, `basePath=/relax`) |
| `/relax-api/` | FastAPI (Unit python) |

`/relax/*` and `/relax-api*` do not overlap (unlike `/relax*` vs `/relax-api`).

```bash
./deploy/silk/install-on-silk.sh
```

See [docs/silk-deploy.md](../../docs/silk-deploy.md).
