"""Hardening checks for public calculator deployment."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.datasets.loader import DatasetCatalog
from app.datasets.user_store import UserDatasetStore
from app.datasets.working_catalog import WorkingCatalog
from app.engine.compiler import CompileError, _sql_func
from app.parsers.relalg import ast as ra


def _client(tmp_path: Path) -> TestClient:
    get_settings.cache_clear()
    data = Path(__file__).resolve().parent.parent / "data" / "local_groups"
    upload = tmp_path / "uploads"
    store = tmp_path / "user_datasets"
    upload.mkdir(parents=True, exist_ok=True)
    store.mkdir(parents=True, exist_ok=True)
    app = create_app()
    users = UserDatasetStore(upload, store, 5 * 1024 * 1024)
    app.state.user_store = users
    app.state.catalog = WorkingCatalog(DatasetCatalog(data), users)
    return TestClient(app)


def test_security_headers_present(tmp_path):
    client = _client(tmp_path)
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert "default-src" in (res.headers.get("content-security-policy") or "")


def test_openapi_disabled_by_default(tmp_path):
    client = _client(tmp_path)
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404


def test_query_rejects_oversized_body(tmp_path):
    client = _client(tmp_path)
    huge = "π_{a}(R);" + ("--" + ("x" * 200) + "\n") * 600
    assert len(huge) > 100_000
    res = client.post(
        "/api/query",
        json={
            "datasetId": "basics",
            "language": "relalg",
            "query": huge,
        },
    )
    assert res.status_code == 422


def test_unknown_function_rejected():
    with pytest.raises(CompileError, match="unsupported function"):
        _sql_func(ra.FuncCall(name="version", args=[]))


def test_rate_limit_query(tmp_path, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "3")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    client = _client(tmp_path)
    payload = {
        "datasetId": "basics",
        "language": "relalg",
        "query": "π_{name}(Employee)",
    }
    codes = [
        client.post("/api/query", json=payload).status_code for _ in range(5)
    ]
    assert 429 in codes
    get_settings.cache_clear()
