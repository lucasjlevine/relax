"""Infer and apply base-relation column type coercions from RelAlg usage."""

from __future__ import annotations

import re
from typing import Any

from app.datasets.loader import GroupDef
from app.parsers.relalg import ast as ra

_COMPARE_OPS = {"=", "!=", "<>", "<", ">", "<=", ">="}
_ARITH_OPS = {"+", "-", "*", "/", "%"}
# Aggregates / helpers that require a numeric argument
_NUMERIC_AGG_FNS = frozenset({"sum", "avg", "min", "max"})
_NUMERIC_FUNCS = frozenset(
    {
        "abs",
        "round",
        "floor",
        "ceil",
        "ceiling",
        "add",
        "sub",
        "mul",
        "div",
        "mod",
        "sum",
        "avg",
        "min",
        "max",
    }
)
_DATE_FUNCS = frozenset(
    {
        "date",
        "adddate",
        "subdate",
    }
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _literal_implied_type(value: Any) -> str | None:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        if _DATE_RE.fullmatch(value.strip()):
            return "date"
    return None


def _column_targets(
    group: GroupDef, ref: ra.ColumnRef
) -> list[tuple[str, str, str]]:
    """Resolve ColumnRef to (relation, column, current_type)."""
    if ref.relation:
        rel = group.relations.get(ref.relation)
        if not rel:
            return []
        for col in rel.columns:
            if col.name == ref.name:
                return [(rel.name, col.name, col.type_name)]
        return []
    matches: list[tuple[str, str, str]] = []
    for rel in group.relations.values():
        for col in rel.columns:
            if col.name == ref.name:
                matches.append((rel.name, col.name, col.type_name))
    return matches


def _collect_column_refs(node: object, out: list[ra.ColumnRef]) -> None:
    if isinstance(node, ra.ColumnRef):
        if node.name != "*":
            out.append(node)
        return
    if isinstance(node, ra.BinaryExpr):
        _collect_column_refs(node.left, out)
        _collect_column_refs(node.right, out)
        return
    if isinstance(node, ra.UnaryExpr):
        _collect_column_refs(node.operand, out)
        return
    if isinstance(node, ra.FuncCall):
        for a in node.args:
            _collect_column_refs(a, out)
        return
    if isinstance(node, ra.CaseExpr):
        for c, r in node.whens:
            _collect_column_refs(c, out)
            _collect_column_refs(r, out)
        if node.else_result is not None:
            _collect_column_refs(node.else_result, out)
        return


def _note_columns(arg: object, to_type: str, out: list[tuple[ra.ColumnRef, str]]) -> None:
    refs: list[ra.ColumnRef] = []
    _collect_column_refs(arg, refs)
    for ref in refs:
        out.append((ref, to_type))


def _walk_expr(node: object, out: list[tuple[ra.ColumnRef, str]]) -> None:
    if isinstance(node, ra.BinaryExpr):
        if node.op in _COMPARE_OPS:
            left, right = node.left, node.right
            if isinstance(left, ra.ColumnRef) and isinstance(right, ra.Literal):
                implied = _literal_implied_type(right.value)
                if implied:
                    out.append((left, implied))
            elif isinstance(right, ra.ColumnRef) and isinstance(left, ra.Literal):
                implied = _literal_implied_type(left.value)
                if implied:
                    out.append((right, implied))
        elif node.op in _ARITH_OPS:
            # col + 1, 2 * col, … → numeric column
            left, right = node.left, node.right
            if isinstance(left, ra.ColumnRef) and isinstance(right, ra.Literal):
                if _literal_implied_type(right.value) == "number":
                    out.append((left, "number"))
            elif isinstance(right, ra.ColumnRef) and isinstance(left, ra.Literal):
                if _literal_implied_type(left.value) == "number":
                    out.append((right, "number"))
            elif isinstance(left, ra.ColumnRef) and isinstance(right, ra.ColumnRef):
                # col_a * col_b — both likely numeric in teaching queries
                out.append((left, "number"))
                out.append((right, "number"))
        _walk_expr(node.left, out)
        _walk_expr(node.right, out)
        return
    if isinstance(node, ra.UnaryExpr):
        _walk_expr(node.operand, out)
        return
    if isinstance(node, ra.FuncCall):
        name = node.name.lower()
        if name in _NUMERIC_FUNCS and node.args:
            # First arg (and second for binary numeric helpers) → number
            _note_columns(node.args[0], "number", out)
            if name in ("add", "sub", "mul", "div", "mod", "round") and len(node.args) > 1:
                _note_columns(node.args[1], "number", out)
        elif name in _DATE_FUNCS and node.args:
            # date()/year()/… first arg → date; adddate/subdate day count → number
            _note_columns(node.args[0], "date", out)
            if name in ("adddate", "subdate") and len(node.args) > 1:
                _note_columns(node.args[1], "number", out)
        for a in node.args:
            _walk_expr(a, out)
        return
    if isinstance(node, ra.CaseExpr):
        for c, r in node.whens:
            _walk_expr(c, out)
            _walk_expr(r, out)
        if node.else_result is not None:
            _walk_expr(node.else_result, out)
        return


def _walk_ra(node: ra.RANode, out: list[tuple[ra.ColumnRef, str]]) -> None:
    if isinstance(node, ra.Statement):
        for _, expr in node.assignments or []:
            _walk_ra(expr, out)
        _walk_ra(node.result, out)
        return
    if isinstance(node, ra.Selection):
        _walk_expr(node.condition, out)
        _walk_ra(node.child, out)
        return
    if isinstance(node, ra.Projection):
        for expr, _ in node.items:
            _walk_expr(expr, out)
        _walk_ra(node.child, out)
        return
    if isinstance(node, ra.OrderBy):
        for expr, _ in node.keys:
            _walk_expr(expr, out)
        _walk_ra(node.child, out)
        return
    if isinstance(node, ra.GroupBy):
        for c in node.group_cols:
            _walk_expr(c, out)
        for fn, arg, _ in node.aggregates:
            if fn.lower() in _NUMERIC_AGG_FNS:
                _note_columns(arg, "number", out)
            _walk_expr(arg, out)
        _walk_ra(node.child, out)
        return
    if isinstance(
        node,
        (
            ra.ThetaJoin,
            ra.LeftOuterJoin,
            ra.RightOuterJoin,
            ra.FullOuterJoin,
            ra.LeftSemiJoin,
            ra.RightSemiJoin,
            ra.AntiJoin,
        ),
    ):
        if getattr(node, "condition", None) is not None:
            _walk_expr(node.condition, out)
        _walk_ra(node.left, out)
        _walk_ra(node.right, out)
        return
    if isinstance(node, ra.BinaryOp):
        _walk_ra(node.left, out)
        _walk_ra(node.right, out)
        return
    if hasattr(node, "child") and isinstance(getattr(node, "child"), ra.RANode):
        _walk_ra(node.child, out)


def infer_type_coercions(
    nodes: list[ra.RANode], group: GroupDef
) -> list[tuple[str, str, str, str]]:
    """
    Return list of (relation, column, from_type, to_type) implied by the query.

    Triggers include comparisons to typed literals, numeric aggregates
    (sum/avg/min/max), numeric helpers, arithmetic, and date helpers.

    Only suggests changes when current type differs from the implied type.
    Unqualified columns that appear in multiple relations are skipped.
    """
    hits: list[tuple[ra.ColumnRef, str]] = []
    for node in nodes:
        _walk_ra(node, hits)

    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str, str, str]] = []
    for ref, to_type in hits:
        targets = _column_targets(group, ref)
        if not targets:
            continue
        if ref.relation is None and len(targets) != 1:
            continue
        for rel_name, col_name, cur in targets:
            key = (rel_name, col_name)
            if key in seen:
                continue
            cur_n = cur.lower()
            if cur_n == to_type:
                continue
            # Only auto-promote string/unknown → more specific types for teaching CSVs
            if cur_n not in ("string", "str", "text", "varchar"):
                if not (cur_n == "number" and to_type == "date"):
                    continue
            seen.add(key)
            result.append((rel_name, col_name, cur_n, to_type))
    return result
