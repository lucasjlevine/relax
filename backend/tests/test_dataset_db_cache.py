"""Dataset DuckDB cache + COUNT shortcut + relation paging."""

from __future__ import annotations

from pathlib import Path

from app.datasets.loader import ColumnDef, GroupDef, RelationDef
import app.engine.dataset_db as dataset_db
from app.engine.dataset_db import (
    clear_all,
    group_fingerprint,
    invalidate,
    open_query_connection,
)
from app.engine.executor import execute_relalg, execute_sql


def _group(n_rows: int = 5) -> GroupDef:
    rows = [[i, f"n{i}"] for i in range(n_rows)]
    return GroupDef(
        id="cache-demo",
        name="Cache Demo",
        updated_at="2026-01-01T00:00:00+00:00",
        relations={
            "T": RelationDef(
                name="T",
                columns=[
                    ColumnDef(name="id", type_name="number"),
                    ColumnDef(name="name", type_name="string"),
                ],
                rows=rows,
            )
        },
    )


def test_cache_hit_reuses_file(tmp_path: Path, monkeypatch) -> None:
    clear_all()
    monkeypatch.setattr(
        "app.engine.dataset_db._cache_root",
        tmp_path / "duck-cache",
    )
    (tmp_path / "duck-cache").mkdir()
    g = _group(20)
    c1 = open_query_connection(g)
    path = dataset_db._cache[g.id].path
    assert path.is_file()
    assert c1.execute("SELECT COUNT(*) FROM T").fetchone()[0] == 20
    c1.close()

    c2 = open_query_connection(g)
    assert dataset_db._cache[g.id].path == path
    assert c2.execute("SELECT COUNT(*) FROM T").fetchone()[0] == 20
    c2.close()


def test_fingerprint_change_rebuilds_cache(tmp_path: Path, monkeypatch) -> None:
    clear_all()
    monkeypatch.setattr(
        "app.engine.dataset_db._cache_root",
        tmp_path / "duck-cache",
    )
    (tmp_path / "duck-cache").mkdir()
    g = _group(3)
    open_query_connection(g).close()
    old_path = dataset_db._cache[g.id].path
    old_fp = group_fingerprint(g)

    g.relations["T"].rows.append([99, "extra"])
    g.updated_at = "2026-01-02T00:00:00+00:00"
    assert group_fingerprint(g) != old_fp

    c = open_query_connection(g)
    assert c.execute("SELECT COUNT(*) FROM T").fetchone()[0] == 4
    c.close()
    assert dataset_db._cache[g.id].path != old_path or not old_path.is_file()
    assert (
        not old_path.is_file()
        or dataset_db._cache[g.id].fingerprint != old_fp
    )


def test_invalidate_drops_entry(tmp_path: Path, monkeypatch) -> None:
    clear_all()
    monkeypatch.setattr(
        "app.engine.dataset_db._cache_root",
        tmp_path / "duck-cache",
    )
    (tmp_path / "duck-cache").mkdir()
    g = _group()
    open_query_connection(g).close()
    path = dataset_db._cache[g.id].path
    invalidate(g.id)
    assert g.id not in dataset_db._cache
    assert not path.is_file()


def test_count_shortcut_when_page_incomplete() -> None:
    clear_all()
    g = _group(5)
    result = execute_relalg(g, "T", limit=100, offset=0)
    assert result.rowCount == 5
    assert len(result.rows) == 5


def test_count_exact_when_page_full() -> None:
    clear_all()
    g = _group(50)
    result = execute_relalg(g, "T", limit=10, offset=0)
    assert result.rowCount == 50
    assert len(result.rows) == 10


def test_sql_shares_cache_path() -> None:
    clear_all()
    g = _group(8)
    a = execute_sql(g, 'SELECT * FROM "T"', limit=100, offset=0)
    b = execute_sql(g, 'SELECT * FROM "T"', limit=100, offset=0)
    assert a.rowCount == b.rowCount == 8


def test_division_cte_semantics() -> None:
    clear_all()
    g = GroupDef(
        id="div-demo",
        name="Div",
        relations={
            "SP": RelationDef(
                name="SP",
                columns=[
                    ColumnDef("sno", "string"),
                    ColumnDef("pno", "string"),
                ],
                rows=[
                    ["S1", "P1"],
                    ["S1", "P2"],
                    ["S2", "P1"],
                    ["S3", "P1"],
                    ["S3", "P2"],
                ],
            ),
            "P": RelationDef(
                name="P",
                columns=[ColumnDef("pno", "string")],
                rows=[["P1"], ["P2"]],
            ),
        },
    )
    result = execute_relalg(g, "SP ÷ P", limit=100, offset=0)
    snos = sorted(str(r[0]) for r in result.rows)
    assert snos == ["S1", "S3"]
