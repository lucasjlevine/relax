from pathlib import Path

from app.datasets.loader import DatasetCatalog
from app.engine.executor import execute_relalg
from app.parsers.relalg.formatter import format_relalg_query
from app.parsers.relalg.parser import parse_relalg
from app.parsers.relalg import ast as ra


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "local_groups"


def test_subscript_parse_and_format():
    q = "π_{a}(σ_{a > 1}(R))"
    node = parse_relalg(q)
    root = node.result if isinstance(node, ra.Statement) else node
    assert isinstance(root, ra.Projection)
    assert "π_{a}" in format_relalg_query("pi a (sigma a > 1 (R))")


def test_left_join_and_order():
    group = DatasetCatalog(DATA_PATH).get("joins")
    result = execute_relalg(
        group,
        "tau title asc (Project left join Assign on Project.pid = Assign.pid)",
        limit=50,
        offset=0,
    )
    assert result.rowCount >= 1
    assert result.tree is not None


def test_format_api_endpoint():
    from fastapi.testclient import TestClient
    from app.main import create_app

    client = TestClient(create_app())
    res = client.post(
        "/api/format",
        json={
            "language": "relalg",
            "query": "pi name (sigma salary > 80000 (Employee))",
        },
    )
    assert res.status_code == 200
    assert "π_{" in res.json()["formatted"]


def test_format_api_humanizes_parse_errors():
    from fastapi.testclient import TestClient
    from app.main import create_app

    client = TestClient(create_app())
    res = client.post(
        "/api/format",
        json={"language": "relalg", "query": "pi ("},
    )
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert detail["code"] == "parse_error"
    assert "AGG_FN" not in detail["message"]
    assert "syntax" in detail["message"].lower() or "early" in detail["message"].lower()


def test_csv_upload():
    from fastapi.testclient import TestClient
    from app.main import create_app

    client = TestClient(create_app())
    csv_body = b"id,name\n1,Ada\n2,Bob\n"
    res = client.post(
        "/api/datasets/upload",
        files={"file": ("people.csv", csv_body, "text/csv")},
        data={
            "relationName": "People",
            "hasHeader": "true",
            "skipRows": "0",
            "delimiter": ",",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["id"].startswith("upload-csv-")
    assert any(r["name"] == "People" for r in body["relations"])

    q = client.post(
        "/api/query",
        json={
            "datasetId": body["id"],
            "language": "relalg",
            "query": "pi name (People)",
        },
    )
    assert q.status_code == 200
    assert q.json()["rowCount"] == 2


def test_csv_upload_skip_and_no_header():
    from fastapi.testclient import TestClient
    from app.main import create_app

    client = TestClient(create_app())
    csv_body = b"skip me\nx,y\n1,a\n2,b\n"
    res = client.post(
        "/api/datasets/upload",
        files={"file": ("raw.csv", csv_body, "text/csv")},
        data={
            "relationName": "T",
            "hasHeader": "false",
            "skipRows": "1",
            "delimiter": ",",
        },
    )
    assert res.status_code == 200
    rel = res.json()["relations"][0]
    assert rel["rowCount"] == 3
    assert rel["columns"][0]["name"] == "col1"


def test_build_relation():
    from fastapi.testclient import TestClient
    from app.main import create_app

    client = TestClient(create_app())
    res = client.post(
        "/api/datasets/build",
        json={
            "name": "Tiny",
            "relationName": "T",
            "columns": [{"name": "x", "type": "number"}, {"name": "y", "type": "string"}],
            "rows": [[1, "a"], [2, "b"]],
        },
    )
    assert res.status_code == 200
    assert res.json()["id"].startswith("custom-")
