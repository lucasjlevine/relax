from pathlib import Path

import pytest

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
