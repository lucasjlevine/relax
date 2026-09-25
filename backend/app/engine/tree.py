from __future__ import annotations

from app.models.schemas import OperatorTreeNode
from app.parsers.relalg import ast as ra


class _IdGen:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return str(self._n)


def _fmt_expr(node: object) -> str:
    if isinstance(node, ra.ColumnRef):
        if node.relation:
            return f"{node.relation}.{node.name}"
        return node.name
    if isinstance(node, ra.Literal):
        if node.value is None:
            return "null"
        if isinstance(node.value, str):
            return repr(node.value)
        return str(node.value)
    if isinstance(node, ra.FuncCall):
        return f"{node.name}({', '.join(_fmt_expr(a) for a in node.args)})"
    if isinstance(node, ra.BinaryExpr):
        return f"{_fmt_expr(node.left)} {node.op} {_fmt_expr(node.right)}"
    if isinstance(node, ra.UnaryExpr):
        return f"{node.op} {_fmt_expr(node.operand)}"
    return str(node)


def build_operator_tree(node: ra.RANode, ids: _IdGen | None = None) -> OperatorTreeNode:
    ids = ids or _IdGen()
    nid = ids.next()

    if isinstance(node, ra.Relation):
        return OperatorTreeNode(id=nid, label=node.name, operator="relation", children=[])

    if isinstance(node, ra.Projection):
        cols = ", ".join(
            _fmt_expr(e) + (f"→{alias}" if alias else "") for e, alias in node.items
        )
        return OperatorTreeNode(
            id=nid,
            label=f"π {cols}",
            operator="projection",
            children=[build_operator_tree(node.child, ids)],
        )

    if isinstance(node, ra.Selection):
        return OperatorTreeNode(
            id=nid,
            label=f"σ {_fmt_expr(node.condition)}",
            operator="selection",
            children=[build_operator_tree(node.child, ids)],
        )

    if isinstance(node, (ra.RenameRelation, ra.RenameColumns)):
        label = (
            f"ρ {node.new_name}"
            if isinstance(node, ra.RenameRelation)
            else "ρ " + ", ".join(f"{a}→{b}" for a, b in node.mapping)
        )
        return OperatorTreeNode(
            id=nid,
            label=label,
            operator="rename",
            children=[build_operator_tree(node.child, ids)],
        )

    if isinstance(node, ra.OrderBy):
        keys = ", ".join(f"{_fmt_expr(e)} {d}" for e, d in node.keys)
        return OperatorTreeNode(
            id=nid,
            label=f"τ {keys}",
            operator="orderby",
            children=[build_operator_tree(node.child, ids)],
        )

    if isinstance(node, ra.GroupBy):
        return OperatorTreeNode(
            id=nid,
            label="γ",
            operator="groupby",
            children=[build_operator_tree(node.child, ids)],
        )

    if isinstance(node, ra.Distinct):
        return OperatorTreeNode(
            id=nid,
            label="δ",
            operator="distinct",
            children=[build_operator_tree(node.child, ids)],
        )

    binary = [
        (ra.Union, "∪", "union"),
        (ra.Intersect, "∩", "intersect"),
        (ra.Except, "−", "except"),
        (ra.Cross, "×", "cross"),
        (ra.NaturalJoin, "⋈", "natural_join"),
        (ra.Division, "÷", "division"),
        (ra.ThetaJoin, "⋈", "theta_join"),
        (ra.LeftOuterJoin, "⟕", "left_outer_join"),
        (ra.RightOuterJoin, "⟖", "right_outer_join"),
        (ra.FullOuterJoin, "⟗", "full_outer_join"),
        (ra.LeftSemiJoin, "⋉", "left_semi_join"),
        (ra.RightSemiJoin, "⋊", "right_semi_join"),
        (ra.AntiJoin, "▷", "anti_join"),
    ]
    for cls, sym, op in binary:
        if isinstance(node, cls):
            label = sym
            cond = getattr(node, "condition", None)
            if cond is not None:
                label = f"{sym} {_fmt_expr(cond)}"
            return OperatorTreeNode(
                id=nid,
                label=label,
                operator=op,
                children=[
                    build_operator_tree(node.left, ids),
                    build_operator_tree(node.right, ids),
                ],
            )

    return OperatorTreeNode(id=nid, label="?", operator="unknown", children=[])
