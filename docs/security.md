# Security notes

Relational Playground is a **teaching calculator**: built-in datasets are public, queries run in an in-memory DuckDB sandbox (`enable_external_access=false`), and user uploads are isolated by an `HttpOnly` / `SameSite=Lax` owner cookie.

## What the public audit got wrong

| Claim | Reality |
|-------|---------|
| SQL injection on `/api/query` | RelAlg is compiled with quoted identifiers and escaped literals; SQL mode is validated with sqlglot and only SELECT-family statements execute. There is no string-concatenated SQL from user input. |
| “Missing authentication” on query | Built-ins are intentionally public. **User datasets require the owner cookie** for read/query/export. Sharing is via unguessable `shr_…` tokens. |
| Share-token enumeration | Tokens are 128-bit random; lookup is by exact key. |
| MySQL `SLEEP` / `information_schema` dumps | Not applicable — execution is DuckDB over registered teaching tables only. |

## Hardening in place

- DuckDB: no external access, memory/thread caps, interruptible query timeout (`QUERY_TIMEOUT_MS`)
- RelAlg: statement count cap, query body max length, allowlisted helper/aggregate functions only
- Owner-scoped dataset GET / export / query (built-ins remain public)
- In-process rate limits on query/format/upload/build/group
- Security headers on API + Next.js (`CSP`, `X-Frame-Options`, `X-Content-Type-Options`, …)
- OpenAPI/docs disabled by default (`EXPOSE_OPENAPI=false`)
- CORS allowlist (never `*` with credentials); methods limited to GET/POST/PATCH/DELETE/OPTIONS
- Generic 500 responses (no stack traces to clients)

## Operator / deploy tips

- Set `CORS_ORIGINS` to the exact public origin (see `deploy/silk/systemd/relax-api.service`).
- Prefer proxy-level rate limits in front of Unit when traffic grows.
- Treat uploaded CSVs as potentially sensitive class data — ownership checks are the access control.
