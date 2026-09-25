from pathlib import Path

import pytest

from app.datasets.loader import DatasetCatalog, DatasetError, parse_local_groups


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "local_groups"


def test_parse_local_groups_file():
    text = DATA_PATH.read_text(encoding="utf-8")
    groups = parse_local_groups(text)
    assert len(groups) >= 3
    names = {g.name for g in groups}
    assert "R, S, T" in names
    assert "University" in names


def test_catalog_get_misc():
    catalog = DatasetCatalog(DATA_PATH)
    group = catalog.get("r-s-t")
    assert "R" in group.relations
    assert group.relations["R"].columns[0].name == "a"
    assert len(group.relations["R"].rows) == 5


def test_catalog_unknown():
    catalog = DatasetCatalog(DATA_PATH)
    with pytest.raises(DatasetError):
        catalog.get("does-not-exist")
