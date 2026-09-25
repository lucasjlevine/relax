from pathlib import Path

import pytest

from app.datasets.loader import DatasetCatalog
from app.engine.executor import QueryError, execute_relalg, execute_sql_query
from app.parsers.sql.validator import SqlValidationError, validate_sql


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "local_groups"


@pytest.fixture
def group():
    return DatasetCatalog(DATA_PATH).get("r-s-t")


def test_validate_select():
    sql = validate_sql("SELECT a FROM R WHERE a > 1")
    assert "SELECT" in sql.upper()


def test_reject_insert():
    with pytest.raises(SqlValidationError):
        validate_sql("INSERT INTO R VALUES (1, 'x', 'y')")


def test_execute_relalg_projection(group):
    result = execute_relalg(group, "pi a (sigma a > 1 (R))", limit=100, offset=0)
    assert result.rowCount == 4
    assert result.columns[0].name == "a"
    assert result.tree is not None
    assert result.tree.operator == "projection"


def test_execute_relalg_join(group):
    result = execute_relalg(group, "R join S", limit=100, offset=0)
    assert result.rowCount > 0
    assert result.tree is not None


def test_execute_sql(group):
    result = execute_sql_query(
        group, "SELECT a FROM R WHERE a > 1", limit=100, offset=0
    )
    assert result.rowCount == 4


def test_execute_relalg_parse_error(group):
    with pytest.raises(QueryError) as exc:
        execute_relalg(group, "pi (", limit=10, offset=0)
    assert exc.value.code == "parse_error"
