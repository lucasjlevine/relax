from pathlib import Path

import pytest

from app.datasets.loader import DatasetCatalog
from app.engine.executor import QueryError, execute_relalg, execute_sql_query
from app.parsers.sql.validator import SqlValidationError, validate_sql


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "local_groups"


@pytest.fixture
def group():
    return DatasetCatalog(DATA_PATH).get("basics")


@pytest.fixture
def joins():
    return DatasetCatalog(DATA_PATH).get("joins")


def test_validate_select():
    sql = validate_sql("SELECT name FROM Employee WHERE salary > 1")
    assert "SELECT" in sql.upper()


def test_reject_insert():
    with pytest.raises(SqlValidationError):
        validate_sql("INSERT INTO Employee VALUES (1, 'x', 'y', 1)")


def test_execute_relalg_projection(group):
    result = execute_relalg(
        group, "pi name (sigma salary > 80000 (Employee))", limit=100, offset=0
    )
    assert result.rowCount == 2
    assert result.columns[0].name == "name"
    assert result.tree is not None
    assert result.tree.operator == "projection"


def test_execute_relalg_join(joins):
    result = execute_relalg(joins, "Project join Assign", limit=100, offset=0)
    assert result.rowCount > 0
    assert result.tree is not None


def test_execute_sql(group):
    result = execute_sql_query(
        group,
        "SELECT name FROM Employee WHERE salary > 80000",
        limit=100,
        offset=0,
    )
    assert result.rowCount == 2


def test_multi_with_and_bare_union(group):
    q = """
    WITH Engineering AS (
      SELECT * FROM Employee WHERE dept = 'Engineering'
    )
    WITH Sales AS (
      SELECT * FROM Employee WHERE dept = 'Sales'
    )
    Engineering UNION ALL Sales
    """
    sql = validate_sql(q)
    assert sql.upper().count("WITH") == 1
    assert "UNION ALL" in sql.upper()
    assert "SELECT * FROM" in sql.upper()
    result = execute_sql_query(group, q, limit=50, offset=0)
    assert result.rowCount >= 2


def test_execute_relalg_parse_error(group):
    with pytest.raises(QueryError) as exc:
        execute_relalg(group, "pi (", limit=10, offset=0)
    assert exc.value.code == "parse_error"
    assert "syntax" in exc.value.message.lower()
    assert "AGG_FN" not in exc.value.message
