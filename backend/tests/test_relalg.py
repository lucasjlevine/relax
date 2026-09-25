import pytest

from app.parsers.relalg.parser import RelAlgParseError, parse_relalg
from app.parsers.relalg import ast as ra
from app.engine.compiler import compile_relalg


def test_parse_selection_projection():
    node = parse_relalg("pi a (sigma a > 1 (R))")
    assert isinstance(node, ra.Projection)
    assert isinstance(node.child, ra.Selection)


def test_parse_unicode_ops():
    node = parse_relalg("π a (σ a > 1 (R))")
    assert isinstance(node, ra.Projection)


def test_parse_natural_join():
    node = parse_relalg("R join S")
    assert isinstance(node, ra.NaturalJoin)


def test_parse_theta_join():
    node = parse_relalg("R join S on a = d")
    assert isinstance(node, ra.ThetaJoin)


def test_parse_set_ops():
    assert isinstance(parse_relalg("R union S"), ra.Union)
    assert isinstance(parse_relalg("R intersect S"), ra.Intersect)
    assert isinstance(parse_relalg("R except S"), ra.Except)


def test_parse_cross():
    node = parse_relalg("R cross S")
    assert isinstance(node, ra.Cross)


def test_parse_error():
    with pytest.raises(RelAlgParseError):
        parse_relalg("pi (")


def test_compile_contains_select():
    sql = compile_relalg(parse_relalg("pi a (R)"))
    assert "SELECT" in sql.upper()
    assert "a" in sql
