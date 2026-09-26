from pathlib import Path

import pytest

from app.datasets.loader import ColumnDef, GroupDef, RelationDef
from app.engine.executor import execute_relalg
from app.engine.type_coerce import infer_type_coercions
from app.parsers.relalg.parser import parse_relalg
from app.parsers.relalg.statements import split_relalg_statements


def test_split_requires_semicolon_for_multi():
    text = """
-- first
π_{a}(R);

-- second
π_{b}(S);
"""
    parts = split_relalg_statements(text)
    assert len(parts) == 2
    assert parts[0][1] == "first"
    assert parts[1][1] == "second"


def test_format_preserves_trailing_comments():
    from app.parsers.relalg.formatter import format_relalg_query

    q = "pi a (R)\n-- keep me"
    out = format_relalg_query(q)
    assert "-- keep me" in out
    assert "π_{a}" in out

    inline = "pi a (R) -- inline note"
    out2 = format_relalg_query(inline)
    assert "-- inline note" in out2

    multi = "pi a (R);\n-- after\npi b (S);\n-- end note"
    out3 = format_relalg_query(multi)
    assert "-- after" in out3
    assert "-- end note" in out3
    assert out3.count(";") >= 2


def test_format_preserves_leading_comments():
    from app.parsers.relalg.formatter import format_relalg_query

    q = "-- Kate titles\n-- second line\npi title (Movie)"
    out = format_relalg_query(q)
    assert "-- Kate titles" in out
    assert "-- second line" in out
    assert "π_{title}" in out


def test_trailing_comment_not_parsed_as_statement():
    """A final ``;`` + comment must not become a second (empty) statement."""
    from app.parsers.relalg.parser import parse_relalg

    q = "π_{a}(R);\n-- keep me"
    parts = split_relalg_statements(q)
    assert len(parts) == 1
    parse_relalg(parts[0][0])

    q2 = "π_{a}(R)\n-- keep me"
    parts2 = split_relalg_statements(q2)
    assert len(parts2) == 1
    parse_relalg(parts2[0][0])

    group = GroupDef(
        id="t",
        name="t",
        relations={
            "R": RelationDef(
                name="R",
                columns=[ColumnDef(name="a", type_name="number")],
                rows=[[1], [2]],
            )
        },
    )
    result = execute_relalg(group, "π_{a}(R);\n-- done", limit=50, offset=0)
    assert result.rowCount == 2


def test_split_single_without_semicolon():
    parts = split_relalg_statements("π_{a}(R)")
    assert len(parts) == 1
    assert parts[0][0] == "π_{a}(R)"


def test_multi_statement_execute():
    group = GroupDef(
        id="t",
        name="t",
        relations={
            "R": RelationDef(
                name="R",
                columns=[
                    ColumnDef(name="a", type_name="number"),
                    ColumnDef(name="b", type_name="number"),
                ],
                rows=[[1, 10], [2, 20]],
            )
        },
    )
    q = "π_{a}(R);\nπ_{b}(σ_{a = 1}(R));"
    result = execute_relalg(group, q, limit=50, offset=0)
    assert len(result.results) == 2
    assert result.results[0].rowCount == 2
    assert result.results[1].rowCount == 1
    assert result.results[1].rows[0][0] == 10


def test_infer_year_number_coercion():
    group = GroupDef(
        id="t",
        name="t",
        relations={
            "Movie": RelationDef(
                name="Movie",
                columns=[
                    ColumnDef(name="title", type_name="string"),
                    ColumnDef(name="year", type_name="string"),
                ],
                rows=[["A", "1958"], ["B", "2001"]],
            )
        },
    )
    ast = parse_relalg("σ_{Movie.year < 1960}(Movie)")
    changes = infer_type_coercions([ast], group)
    assert changes == [("Movie", "year", "string", "number")]


def test_infer_avg_coerces_string_to_number():
    group = GroupDef(
        id="t",
        name="t",
        relations={
            "Ratings": RelationDef(
                name="Ratings",
                columns=[
                    ColumnDef(name="mov_id", type_name="number"),
                    ColumnDef(name="rev_stars", type_name="string"),
                ],
                rows=[[1, "4"], [1, "5"], [2, "3"]],
            ),
            "Movie": RelationDef(
                name="Movie",
                columns=[
                    ColumnDef(name="mov_id", type_name="number"),
                    ColumnDef(name="year", type_name="string"),
                ],
                rows=[[1, "1999"], [2, "2001"]],
            ),
        },
    )
    q = "γ_{Movie.year; avg(Ratings.rev_stars) → AverageStars}(Movie ⋈ Ratings)"
    changes = infer_type_coercions([parse_relalg(q)], group)
    assert ("Ratings", "rev_stars", "string", "number") in changes


def test_execute_avg_after_string_coercion():
    group = GroupDef(
        id="t",
        name="t",
        relations={
            "Ratings": RelationDef(
                name="Ratings",
                columns=[
                    ColumnDef(name="year", type_name="number"),
                    ColumnDef(name="rev_stars", type_name="string"),
                ],
                rows=[[1999, "4"], [1999, "5"], [2001, "3"]],
            )
        },
    )
    ast = parse_relalg("γ_{year; avg(rev_stars) → AverageStars}(Ratings)")
    changes = infer_type_coercions([ast], group)
    assert changes == [("Ratings", "rev_stars", "string", "number")]
    rel = group.relations["Ratings"]
    rel.columns[1].type_name = "number"
    rel.rows = [[1999, 4.0], [1999, 5.0], [2001, 3.0]]
    result = execute_relalg(
        group,
        "γ_{year; avg(rev_stars) → AverageStars}(Ratings)",
        limit=50,
        offset=0,
    )
    assert result.rowCount == 2
    by_year = {int(r[0]): float(r[1]) for r in result.rows}
    assert by_year[1999] == 4.5
    assert by_year[2001] == 3.0


def test_infer_sum_min_max_and_arith():
    group = GroupDef(
        id="t",
        name="t",
        relations={
            "R": RelationDef(
                name="R",
                columns=[
                    ColumnDef(name="a", type_name="string"),
                    ColumnDef(name="b", type_name="string"),
                ],
                rows=[["1", "2"]],
            )
        },
    )
    assert ("R", "a", "string", "number") in infer_type_coercions(
        [parse_relalg("γ_{; sum(a)}(R)")], group
    )
    assert ("R", "a", "string", "number") in infer_type_coercions(
        [parse_relalg("γ_{; min(a)}(R)")], group
    )
    assert ("R", "a", "string", "number") in infer_type_coercions(
        [parse_relalg("π_{a + 1}(R)")], group
    )
    assert ("R", "a", "string", "number") in infer_type_coercions(
        [parse_relalg("π_{abs(a)}(R)")], group
    )


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "local_groups"


def test_query_api_multi_and_coerce(tmp_path):
    from fastapi.testclient import TestClient
    from tests.test_api import _client

    client = _client(tmp_path)
    # Build a small movie-like dataset
    built = client.post(
        "/api/datasets/build",
        json={
            "name": "Films",
            "relationName": "Movie",
            "columns": [
                {"name": "title", "type": "string"},
                {"name": "year", "type": "string"},
            ],
            "rows": [["Old", "1958"], ["New", "2001"]],
        },
    )
    assert built.status_code == 200
    ds = built.json()["id"]

    q = """
-- before 1960
π_{Movie.title, Movie.year}(σ_{Movie.year < 1960}(Movie));

-- after 1990
π_{Movie.title, Movie.year}(σ_{Movie.year > 1990}(Movie));
"""
    res = client.post(
        "/api/query",
        json={"datasetId": ds, "language": "relalg", "query": q},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["results"]) == 2
    assert body["results"][0]["rowCount"] == 1
    assert body["results"][0]["rows"][0][0] == "Old"
    assert body["results"][1]["rowCount"] == 1
    assert any("Converted Movie.year" in w for w in body["warnings"])
    detail = client.get(f"/api/datasets/{ds}").json()
    year_col = next(
        c
        for r in detail["relations"]
        if r["name"] == "Movie"
        for c in r["columns"]
        if c["name"] == "year"
    )
    assert year_col["type"] == "number"
