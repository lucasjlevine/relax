from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.datasets.loader import DatasetCatalog
from app.datasets.user_store import UserDatasetStore
from app.datasets.working_catalog import WorkingCatalog


def _client() -> TestClient:
    app = create_app()
    data = Path(__file__).resolve().parent.parent / "data" / "local_groups"
    upload = Path(__file__).resolve().parent.parent / "data" / "uploads"
    static = DatasetCatalog(data)
    users = UserDatasetStore(upload, 5 * 1024 * 1024)
    app.state.user_store = users
    app.state.catalog = WorkingCatalog(static, users)
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
    assert ids >= {"basics", "joins", "setops", "aggregates", "library"}


def test_get_dataset():
    client = _client()
    res = client.get("/api/datasets/basics")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Basics"
    assert any(r["name"] == "Employee" for r in body["relations"])


def test_query_relalg():
    client = _client()
    res = client.post(
        "/api/query",
        json={
            "datasetId": "basics",
            "language": "relalg",
            "query": "pi name (sigma salary > 80000 (Employee))",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["rowCount"] == 2
    assert body["tree"]["operator"] == "projection"


def test_query_sql():
    client = _client()
    res = client.post(
        "/api/query",
        json={
            "datasetId": "basics",
            "language": "sql",
            "query": "SELECT name FROM Employee WHERE salary > 80000",
        },
    )
    assert res.status_code == 200
    assert res.json()["rowCount"] == 2


def test_rename_and_row_ops():
    client = _client()
    renamed = client.patch(
        "/api/datasets/basics",
        json={"name": "Employees"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Employees"

    added = client.post(
        "/api/datasets/basics/relations/Employee/rows",
        json={"values": [6, "Fran", "HR", 70000]},
    )
    assert added.status_code == 200
    emp = next(r for r in added.json()["relations"] if r["name"] == "Employee")
    assert emp["rowCount"] == 6

    deleted = client.delete("/api/datasets/basics/relations/Employee/rows/5")
    assert deleted.status_code == 200
    emp = next(r for r in deleted.json()["relations"] if r["name"] == "Employee")
    assert emp["rowCount"] == 5

    gone = client.delete("/api/datasets/basics")
    assert gone.status_code == 200
    assert client.get("/api/datasets/basics").status_code == 404


def test_columns_and_add_relation():
    client = _client()
    renamed = client.patch(
        "/api/datasets/basics/relations/Employee/columns/dept",
        json={"name": "department"},
    )
    assert renamed.status_code == 200
    emp = next(r for r in renamed.json()["relations"] if r["name"] == "Employee")
    assert any(c["name"] == "department" for c in emp["columns"])
    assert all(c["name"] != "dept" for c in emp["columns"])

    dropped = client.delete(
        "/api/datasets/basics/relations/Employee/columns/salary"
    )
    assert dropped.status_code == 200
    emp = next(r for r in dropped.json()["relations"] if r["name"] == "Employee")
    assert all(c["name"] != "salary" for c in emp["columns"])

    typed = client.patch(
        "/api/datasets/basics/relations/Employee/columns/eid",
        json={"type": "string"},
    )
    assert typed.status_code == 200
    emp = next(r for r in typed.json()["relations"] if r["name"] == "Employee")
    eid = next(c for c in emp["columns"] if c["name"] == "eid")
    assert eid["type"] == "string"


def test_currency_string_to_number():
    client = _client()
    csv_body = b"Bottle_With_GST\n$50\n$12.5\n\"$1,200\"\nbad\n"
    up = client.post(
        "/api/datasets/upload",
        files={"file": ("wine.csv", csv_body, "text/csv")},
        data={"relationName": "Wine", "hasHeader": "true"},
    )
    assert up.status_code == 200
    ds = up.json()["id"]
    typed = client.patch(
        f"/api/datasets/{ds}/relations/Wine/columns/Bottle_With_GST",
        json={"type": "number"},
    )
    assert typed.status_code == 200
    data = client.get(f"/api/datasets/{ds}/relations/Wine").json()
    assert data["columns"][0]["type"] == "number"
    assert data["rows"] == [[50], [12.5], [1200], [None]]

    added = client.post(
        f"/api/datasets/{ds}/relations/Wine/columns",
        json={"name": "note", "type": "string", "default": "ok"},
    )
    assert added.status_code == 200
    wine = next(r for r in added.json()["relations"] if r["name"] == "Wine")
    assert any(c["name"] == "note" for c in wine["columns"])

    created = client.post(
        "/api/datasets/basics/relations",
        json={
            "relationName": "Dept",
            "columns": [
                {"name": "dname", "type": "string"},
                {"name": "floor", "type": "number"},
            ],
            "rows": [["Engineering", 3]],
        },
    )
    assert created.status_code == 200
    names = {r["name"] for r in created.json()["relations"]}
    assert "Dept" in names and "Employee" in names

    csv_body = b"aid,title\n1,Lead\n2,Intern\n"
    uploaded = client.post(
        "/api/datasets/basics/upload",
        files={"file": ("roles.csv", csv_body, "text/csv")},
        data={"relationName": "Role", "hasHeader": "true"},
    )
    assert uploaded.status_code == 200
    names = {r["name"] for r in uploaded.json()["relations"]}
    assert "Role" in names
    role = next(r for r in uploaded.json()["relations"] if r["name"] == "Role")
    assert role["rowCount"] == 2
