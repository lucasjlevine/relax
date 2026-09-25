from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.datasets.loader import DatasetCatalog


def _client() -> TestClient:
    app = create_app()
    data = Path(__file__).resolve().parent.parent / "data" / "local_groups"
    app.state.catalog = DatasetCatalog(data)
    return TestClient(app)


def test_health():
    client = _client()
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_list_datasets():
    client = _client()
    res = client.get("/api/datasets")
    assert res.status_code == 200
    ids = {d["id"] for d in res.json()["datasets"]}
    assert "r-s-t" in ids


def test_get_dataset():
    client = _client()
    res = client.get("/api/datasets/r-s-t")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "R, S, T"
    assert any(r["name"] == "R" for r in body["relations"])


def test_query_relalg():
    client = _client()
    res = client.post(
        "/api/query",
        json={
            "datasetId": "r-s-t",
            "language": "relalg",
            "query": "pi a (sigma a > 1 (R))",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["rowCount"] == 4
    assert body["tree"]["operator"] == "projection"


def test_query_sql():
    client = _client()
    res = client.post(
        "/api/query",
        json={
            "datasetId": "r-s-t",
            "language": "sql",
            "query": "SELECT a FROM R WHERE a > 1",
        },
    )
    assert res.status_code == 200
    assert res.json()["rowCount"] == 4
