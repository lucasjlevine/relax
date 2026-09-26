from app.datasets.loader import DatasetCatalog
from app.engine.executor import execute_relalg
from app.engine.messages import humanize_query_error, humanize_parse_error
from app.parsers.relalg.formatter import format_relalg_query
from app.parsers.relalg.parser import parse_relalg
from pathlib import Path


DATA = Path(__file__).resolve().parent.parent / "data" / "local_groups"


def test_humanize_unknown_column():
    msg = humanize_query_error(
        'Binder Error: Referenced column "foo" not found in FROM clause!'
    )
    assert "Unknown attribute" in msg
    assert "foo" in msg
    assert "Binder" not in msg


def test_humanize_eof_parse():
    raw = (
        "Unexpected end-of-input. Expected one of: \n"
        "\t* NUMBER\n\t* STRING\n\t* NULL\n\t* AGG_FN\n\t* NAME\n"
    )
    msg = humanize_parse_error(raw)
    assert "ends too early" in msg.lower() or "syntax error" in msg.lower()
    assert "NAME" not in msg or "name" in msg.lower()
    assert "AGG_FN" not in msg


def test_humanize_sql_forbidden():
    msg = humanize_query_error(
        "Statement type not allowed: Insert", language="sql"
    )
    assert "SELECT" in msg
    assert "Insert" not in msg


def test_humanize_unexpected_token_no_lark_names():
    raw = "Unexpected token Token('RPAR', ')') at line 1 col 5.\nExpected one of:\n\t* NAME\n\t* LPAR"
    msg = humanize_parse_error(raw)
    assert "syntax error" in msg.lower()
    assert "LPAR" not in msg
    assert "NAME" not in msg or "name" in msg.lower()


def test_rownum_and_string_helpers():
    group = DatasetCatalog(DATA).get("basics")
    result = execute_relalg(
        group, "π_{name}(σ_{rownum() < 2}(Employee))", limit=10, offset=0
    )
    assert result.rowCount == 2

    uppered = execute_relalg(
        group, "π_{upper(name)→n}(Employee)", limit=10, offset=0
    )
    assert uppered.rowCount >= 1
    assert all(isinstance(r[0], str) and r[0] == r[0].upper() for r in uppered.rows)


def test_mod_operator():
    group = DatasetCatalog(DATA).get("basics")
    result = execute_relalg(
        group, "π_{salary % 1000→m}(Employee)", limit=5, offset=0
    )
    assert result.rowCount >= 1


def test_case_when():
    group = DatasetCatalog(DATA).get("basics")
    result = execute_relalg(
        group,
        "π_{name, CASE WHEN salary > 80000 THEN 'high' ELSE 'ok' END→band}(Employee)",
        limit=20,
        offset=0,
    )
    assert result.rowCount >= 1
    assert any(r[1] in ("high", "ok") for r in result.rows)


def test_assignments_step_by_step():
    group = DatasetCatalog(DATA).get("basics")
    query = """
EngineerNames = π_{name}(
  σ_{dept = 'Engineering'}(Employee)
)

SalesNames = π_{name}(
  σ_{dept = 'Sales'}(Employee)
)

SalesAndEngineerNames = EngineerNames ∪ SalesNames
"""
    result = execute_relalg(group, query, limit=50, offset=0)
    assert result.rowCount >= 1
    names = {r[0] for r in result.rows}
    assert names

    ast = parse_relalg(query)
    assert ast.assignments and len(ast.assignments) == 3
    formatted = format_relalg_query(query)
    assert "EngineerNames =" in formatted
    assert "∪" in formatted
