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


def test_qualified_attribute_on_base_relation(group):
    result = execute_relalg(
        group,
        "π_{Employee.name}(σ_{Employee.dept = 'Engineering'}(Employee))",
        limit=100,
        offset=0,
    )
    assert result.rowCount == 2
    assert {row[0] for row in result.rows} == {"Ana", "Cara"}


def test_qualified_attributes_in_selection(joins):
    # Relation.attr in σ over a base relation (user's Director.fname pattern).
    q = (
        "π_{title}("
        "  Project ⋈ "
        "  σ_{Assign.name = 'Ana' ∧ Assign.role = 'Lead'}(Assign)"
        ")"
    )
    result = execute_relalg(joins, q, limit=100, offset=0)
    assert result.rowCount >= 1
    assert result.columns[0].name == "title"
    assert "Website" in {row[0] for row in result.rows}


def test_qualified_theta_join(joins):
    result = execute_relalg(
        joins,
        "π_{title, name}(Project ⋈ Assign on Project.pid = Assign.pid)",
        limit=100,
        offset=0,
    )
    assert result.rowCount > 0
    # Subscript-after-right form also used by the grammar
    result2 = execute_relalg(
        joins,
        "π_{title}(Project ⋈ Assign _{Project.pid = Assign.pid})",
        limit=100,
        offset=0,
    )
    assert result2.rowCount > 0


def test_actor_vs_director_fname_after_joins():
    """Homonymous Relation.attr must resolve to the named relation's column."""
    from app.datasets.loader import ColumnDef, GroupDef, RelationDef

    group = GroupDef(
        id="mad",
        name="Movies",
        relations={
            "Movie": RelationDef(
                name="Movie",
                columns=[
                    ColumnDef("mov_id", "number"),
                    ColumnDef("title", "string"),
                ],
                rows=[[1, "Titanic"]],
            ),
            "Direction": RelationDef(
                name="Direction",
                columns=[
                    ColumnDef("mov_id", "number"),
                    ColumnDef("dir_id", "number"),
                ],
                rows=[[1, 10]],
            ),
            "Director": RelationDef(
                name="Director",
                columns=[
                    ColumnDef("dir_id", "number"),
                    ColumnDef("fname", "string"),
                    ColumnDef("lname", "string"),
                ],
                rows=[[10, "James", "Cameron"]],
            ),
            "Cast": RelationDef(
                name="Cast",
                columns=[
                    ColumnDef("mov_id", "number"),
                    ColumnDef("act_id", "number"),
                ],
                rows=[[1, 20]],
            ),
            "Actor": RelationDef(
                name="Actor",
                columns=[
                    ColumnDef("act_id", "number"),
                    ColumnDef("fname", "string"),
                    ColumnDef("lname", "string"),
                ],
                rows=[[20, "Kate", "Winslet"]],
            ),
        },
    )
    q = (
        "π_{Movie.title, Actor.fname, Actor.lname}("
        "  (((Movie ⋈ Direction)"
        "    ⋈ σ_{Director.fname = 'James' ∧ Director.lname = 'Cameron'}(Director))"
        "   ⋈_{Movie.mov_id = Cast.mov_id} Cast)"
        "  ⋈_{Cast.act_id = Actor.act_id} Actor"
        ")"
    )
    result = execute_relalg(group, q, limit=50, offset=0)
    assert result.rowCount == 1
    assert result.rows[0] == ["Titanic", "Kate", "Winslet"]

    # Selection on Actor.fname must not match Director.fname
    q2 = (
        "π_{Movie.title, Actor.fname}("
        "  σ_{Actor.fname = 'Kate'}("
        "    (((Movie ⋈ Direction) ⋈ Director)"
        "     ⋈_{Movie.mov_id = Cast.mov_id} Cast)"
        "    ⋈_{Cast.act_id = Actor.act_id} Actor"
        "  )"
        ")"
    )
    result2 = execute_relalg(group, q2, limit=50, offset=0)
    assert result2.rowCount == 1
    assert result2.rows[0][1] == "Kate"


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
