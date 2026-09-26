import pytest

from app.parsers.relalg.parser import RelAlgParseError, parse_relalg
from app.parsers.relalg import ast as ra
from app.engine.compiler import compile_relalg


def _root(node: ra.RANode) -> ra.RANode:
    return node.result if isinstance(node, ra.Statement) else node


def test_parse_selection_projection():
    node = _root(parse_relalg("pi a (sigma a > 1 (R))"))
    assert isinstance(node, ra.Projection)
    assert isinstance(node.child, ra.Selection)


def test_parse_unicode_ops():
    node = _root(parse_relalg("π a (σ a > 1 (R))"))
    assert isinstance(node, ra.Projection)


def test_parse_natural_join():
    node = _root(parse_relalg("R join S"))
    assert isinstance(node, ra.NaturalJoin)


def test_parse_theta_join():
    node = _root(parse_relalg("R join S on a = d"))
    assert isinstance(node, ra.ThetaJoin)


def test_parse_theta_join_classical_subscript():
    """RelaX form: R ⋈_{cond} S (condition between operator and right)."""
    node = _root(parse_relalg("R ⋈_{R.a = S.a} S"))
    assert isinstance(node, ra.ThetaJoin)
    nested = _root(
        parse_relalg(
            "π_{Movie.title}("
            "  Movie ⋈_{Movie.mov_id = Cast.mov_id} Cast "
            "  ⋈_{act_id = Actor.act_id} Actor"
            ")"
        )
    )
    assert isinstance(nested, ra.Projection)
    assert isinstance(nested.child, ra.ThetaJoin)


def test_parse_theta_join_trailing_subscript():
    node = _root(parse_relalg("R ⋈ S _{R.a = S.a}"))
    assert isinstance(node, ra.ThetaJoin)


def test_parse_set_ops():
    assert isinstance(_root(parse_relalg("R union S")), ra.Union)
    assert isinstance(_root(parse_relalg("R intersect S")), ra.Intersect)
    assert isinstance(_root(parse_relalg("R except S")), ra.Except)


def test_parse_cross():
    node = _root(parse_relalg("R cross S"))
    assert isinstance(node, ra.Cross)


def test_parse_error():
    with pytest.raises(RelAlgParseError):
        parse_relalg("pi (")


def test_compile_contains_select():
    sql = compile_relalg(parse_relalg("pi a (R)"))
    assert "SELECT" in sql.upper()
    assert "a" in sql


def test_compile_unqualifies_relation_dot_attr():
    sql = compile_relalg(parse_relalg("π_{R.a}(σ_{R.a > 1}(R))"))
    # Nested subquery aliases are synthetic; Relation.attr must become bare columns.
    assert '"R"."a"' not in sql
    assert '"a"' in sql


def test_compile_null_equality_to_is_null():
    """RelAlg ``= null`` / ``!= null`` must become IS [NOT] NULL (any type)."""
    eq = compile_relalg(parse_relalg("σ_{rev_name = null}(Reviewer)"))
    assert 'IS NULL' in eq
    assert '= NULL' not in eq

    ne = compile_relalg(parse_relalg("σ_{rev_name ≠ null}(Reviewer)"))
    assert "IS NOT NULL" in ne

    flipped = compile_relalg(parse_relalg("σ_{null = year}(Movie)"))
    assert "IS NULL" in flipped

    both = compile_relalg(parse_relalg("σ_{null = null}(R)"))
    assert "TRUE" in both.upper()


def test_execute_null_comparisons_all_types():
    from app.datasets.loader import ColumnDef, GroupDef, RelationDef
    from app.engine.executor import execute_relalg

    group = GroupDef(
        id="nulls",
        name="Nulls",
        relations={
            "T": RelationDef(
                name="T",
                columns=[
                    ColumnDef("s", "string"),
                    ColumnDef("n", "number"),
                    ColumnDef("b", "boolean"),
                ],
                rows=[
                    ["a", 1, True],
                    [None, None, None],
                    ["", 0, False],
                ],
            )
        },
    )
    null_s = execute_relalg(group, "σ_{s = null}(T)", limit=50, offset=0)
    assert null_s.rowCount == 1
    assert null_s.rows[0][0] is None

    null_n = execute_relalg(group, "σ_{n = null}(T)", limit=50, offset=0)
    assert null_n.rowCount == 1
    assert null_n.rows[0][1] is None

    null_b = execute_relalg(group, "σ_{b ≠ null}(T)", limit=50, offset=0)
    assert null_b.rowCount == 2

    empty_s = execute_relalg(group, 'σ_{s = ""}(T)', limit=50, offset=0)
    assert empty_s.rowCount == 1
    assert empty_s.rows[0][0] == ""
