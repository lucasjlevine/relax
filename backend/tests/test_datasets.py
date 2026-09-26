from pathlib import Path

import pytest

from app.datasets.group_format import format_group_text
from app.datasets.loader import DatasetCatalog, DatasetError, parse_local_groups


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "local_groups"


def test_parse_local_groups_file():
    text = DATA_PATH.read_text(encoding="utf-8")
    groups = parse_local_groups(text)
    assert len(groups) == 5
    names = {g.name for g in groups}
    assert names == {"Basics", "Joins", "SetOps", "Aggregates", "Library"}


def test_catalog_get_basics():
    catalog = DatasetCatalog(DATA_PATH)
    group = catalog.get("basics")
    assert "Employee" in group.relations
    assert group.relations["Employee"].columns[0].name == "eid"
    assert len(group.relations["Employee"].rows) == 5
    assert "π_{name}" in (group.example_relalg or "")


def test_catalog_unknown():
    catalog = DatasetCatalog(DATA_PATH)
    with pytest.raises(DatasetError):
        catalog.get("does-not-exist")


RELAX_SAMPLE = """
group: sample group
description:this is the description

exampleSql - {
  Select * from A where a = 1
}

exampleRelAlg - {
  σ_{a = 1}(A)
}

A = {a:number, b:number
 1, 2
 3, 4
}
B = {a:number, c:string, d:date
 1, 'test', 1970-01-01
 3, 'test2', null
}
C = A × B
"""


def test_parse_relax_examples_and_derived():
    groups = parse_local_groups(RELAX_SAMPLE)
    assert len(groups) == 1
    g = groups[0]
    assert g.name == "sample group"
    assert g.example_sql and "Select * from A" in g.example_sql
    assert g.example_relalg and "σ_" in g.example_relalg
    assert set(g.relations) == {"A", "B", "C"}
    assert len(g.relations["C"].rows) == 4


def test_format_roundtrip_basics():
    catalog = DatasetCatalog(DATA_PATH)
    text = format_group_text(catalog.get("basics"))
    groups = parse_local_groups(text)
    assert len(groups) == 1
    assert groups[0].name == "Basics"
    assert "Employee" in groups[0].relations
