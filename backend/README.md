# relax backend

FastAPI service that parses RelAlg (Lark) and SQL (sqlglot), then executes against DuckDB.

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
pytest
```
