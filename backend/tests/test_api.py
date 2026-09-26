from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.datasets.loader import DatasetCatalog
from app.datasets.user_store import UserDatasetStore
from app.datasets.working_catalog import WorkingCatalog


def _client(tmp_path: Path | None = None) -> TestClient:
    app = create_app()
    data = Path(__file__).resolve().parent.parent / "data" / "local_groups"
    base = tmp_path or (Path(__file__).resolve().parent.parent / "data")
    upload = base / "uploads"
    store = base / "user_datasets"
    upload.mkdir(parents=True, exist_ok=True)
    store.mkdir(parents=True, exist_ok=True)
    static = DatasetCatalog(data)
    users = UserDatasetStore(upload, store, 5 * 1024 * 1024)
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


def test_mutate_builtin_forks(tmp_path):
    client = _client(tmp_path)
    renamed = client.patch(
        "/api/datasets/basics",
        json={"name": "Employees"},
    )
    assert renamed.status_code == 200
    body = renamed.json()
    assert body["name"] == "Employees"
    assert body["id"] != "basics"
    assert body["forkedFrom"] == "basics"
    assert body["owned"] is True
    assert body["shareToken"]

    # Original built-in still present and unchanged
    original = client.get("/api/datasets/basics")
    assert original.status_code == 200
    assert original.json()["name"] == "Basics"

    added = client.post(
        f"/api/datasets/{body['id']}/relations/Employee/rows",
        json={"values": [6, "Fran", "HR", 70000]},
    )
    assert added.status_code == 200
    emp = next(r for r in added.json()["relations"] if r["name"] == "Employee")
    assert emp["rowCount"] == 6

    deleted = client.delete(
        f"/api/datasets/{body['id']}/relations/Employee/rows/5"
    )
    assert deleted.status_code == 200

    gone = client.delete(f"/api/datasets/{body['id']}")
    assert gone.status_code == 200
    assert client.get(f"/api/datasets/{body['id']}").status_code == 404


def test_column_ops_on_fork(tmp_path):
    client = _client(tmp_path)
    forked = client.patch(
        "/api/datasets/basics",
        json={"name": "Basics copy"},
    ).json()
    ds = forked["id"]

    renamed = client.patch(
        f"/api/datasets/{ds}/relations/Employee/columns/dept",
        json={"name": "department"},
    )
    assert renamed.status_code == 200
    emp = next(r for r in renamed.json()["relations"] if r["name"] == "Employee")
    assert any(c["name"] == "department" for c in emp["columns"])

    dropped = client.delete(
        f"/api/datasets/{ds}/relations/Employee/columns/salary"
    )
    assert dropped.status_code == 200

    typed = client.patch(
        f"/api/datasets/{ds}/relations/Employee/columns/eid",
        json={"type": "string"},
    )
    assert typed.status_code == 200


def test_upload_persists(tmp_path):
    client = _client(tmp_path)
    csv_bytes = b"Bottle_With_GST\n$12.50\n"
    up = client.post(
        "/api/datasets/upload",
        files={"file": ("wine.csv", csv_bytes, "text/csv")},
        data={"relationName": "Wine"},
    )
    assert up.status_code == 200
    ds = up.json()["id"]
    assert ds.startswith("ds_")
    assert (tmp_path / "user_datasets" / f"{ds}.json").exists()

    typed = client.patch(
        f"/api/datasets/{ds}/relations/Wine/columns/Bottle_With_GST",
        json={"type": "number"},
    )
    assert typed.status_code == 200
    data = client.get(f"/api/datasets/{ds}/relations/Wine").json()
    assert data["rows"][0][0] == 12.5

    added = client.post(
        f"/api/datasets/{ds}/relations/Wine/columns",
        json={"name": "note", "type": "string", "default": "ok"},
    )
    assert added.status_code == 200


def test_add_relation_and_csv_into_fork(tmp_path):
    client = _client(tmp_path)
    forked = client.patch(
        "/api/datasets/basics", json={"name": "Basics+"}
    ).json()
    ds = forked["id"]

    created = client.post(
        f"/api/datasets/{ds}/relations",
        json={
            "relationName": "Extra",
            "columns": [{"name": "x", "type": "number"}],
            "rows": [[1]],
        },
    )
    assert created.status_code == 200
    names = {r["name"] for r in created.json()["relations"]}
    assert "Extra" in names

    uploaded = client.post(
        f"/api/datasets/{ds}/upload",
        files={"file": ("role.csv", b"role\nLead\n", "text/csv")},
        data={"relationName": "Role"},
    )
    assert uploaded.status_code == 200
    names = {r["name"] for r in uploaded.json()["relations"]}
    assert "Role" in names


def test_list_hides_other_owner(tmp_path):
    a = _client(tmp_path)
    b = TestClient(a.app)  # same app, but cookies are per client

    up = a.post(
        "/api/datasets/upload",
        files={"file": ("a.csv", b"x\n1\n", "text/csv")},
        data={"relationName": "A"},
    )
    assert up.status_code == 200
    ds = up.json()["id"]

    # Client A sees the dataset
    ids_a = {d["id"] for d in a.get("/api/datasets").json()["datasets"]}
    assert ds in ids_a

    # Client B (no shared cookies) does not list it
    ids_b = {d["id"] for d in b.get("/api/datasets").json()["datasets"]}
    assert ds not in ids_b
    # But can still open by id if known
    assert b.get(f"/api/datasets/{ds}").status_code == 200


def test_share_copy(tmp_path):
    owner = _client(tmp_path)
    up = owner.post(
        "/api/datasets/upload",
        files={"file": ("s.csv", b"n\nhello\n", "text/csv")},
        data={"relationName": "S"},
    ).json()
    token = up["shareToken"]
    assert token

    guest = TestClient(owner.app)
    preview = guest.get(f"/api/datasets/share/{token}")
    assert preview.status_code == 200
    assert preview.json()["name"] == up["name"]

    copied = guest.post(f"/api/datasets/share/{token}/copy")
    assert copied.status_code == 200
    assert copied.json()["id"] != up["id"]
    assert copied.json()["owned"] is True
    ids = {d["id"] for d in guest.get("/api/datasets").json()["datasets"]}
    assert copied.json()["id"] in ids


def test_persist_reload(tmp_path):
    client = _client(tmp_path)
    up = client.post(
        "/api/datasets/upload",
        files={"file": ("p.csv", b"a\n9\n", "text/csv")},
        data={"relationName": "P"},
    ).json()
    ds = up["id"]
    owner_cookie = client.cookies.get("relax_owner")

    # New store instance on same directory
    app2 = create_app()
    data = Path(__file__).resolve().parent.parent / "data" / "local_groups"
    users = UserDatasetStore(
        tmp_path / "uploads", tmp_path / "user_datasets", 5 * 1024 * 1024
    )
    app2.state.user_store = users
    app2.state.catalog = WorkingCatalog(DatasetCatalog(data), users)
    client2 = TestClient(app2)
    if owner_cookie:
        client2.cookies.set("relax_owner", owner_cookie)
    listed = client2.get("/api/datasets").json()["datasets"]
    assert any(d["id"] == ds for d in listed)
