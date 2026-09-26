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
