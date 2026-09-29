# Silk packaging (jlhorton)

Repo: **`~/www-root/relax`**. Config: **`~/www-root/.silk.ini`**.

## Layout

| Piece | How it runs |
|-------|-------------|
| UI | **Static** Next export → `[general] document-root` |
| API | **One** Python Unit app → `uri = /api*` |

We do **not** run a Node Unit app. A catch-all Next `/*` app was stealing `/api`.

**Guide:** [docs/silk-deploy.md](../../docs/silk-deploy.md)

```bash
cd ~/www-root/relax
./deploy/silk/install-on-silk.sh
```
