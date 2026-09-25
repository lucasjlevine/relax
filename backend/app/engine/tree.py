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

    if isinstance(node, ra.RenameRelation):
        return OperatorTreeNode(
            id=nid,
            label=f"ρ {node.new_name}",
            operator="rename",
            children=[build_operator_tree(node.child, ids)],
        )

    if isinstance(node, ra.RenameColumns):
        mapping = ", ".join(f"{a}→{b}" for a, b in node.mapping)
        return OperatorTreeNode(
            id=nid,
            label=f"ρ {mapping}",
            operator="rename",
            children=[build_operator_tree(node.child, ids)],
        )

    if isinstance(node, ra.Union):
        return OperatorTreeNode(
            id=nid,
            label="∪",
            operator="union",
            children=[
                build_operator_tree(node.left, ids),
                build_operator_tree(node.right, ids),
            ],
        )

    if isinstance(node, ra.Intersect):
        return OperatorTreeNode(
            id=nid,
            label="∩",
            operator="intersect",
            children=[
                build_operator_tree(node.left, ids),
                build_operator_tree(node.right, ids),
            ],
        )

    if isinstance(node, ra.Except):
        return OperatorTreeNode(
            id=nid,
            label="−",
            operator="except",
            children=[
                build_operator_tree(node.left, ids),
                build_operator_tree(node.right, ids),
            ],
        )

    if isinstance(node, ra.Cross):
        return OperatorTreeNode(
            id=nid,
            label="×",
            operator="cross",
            children=[
                build_operator_tree(node.left, ids),
                build_operator_tree(node.right, ids),
            ],
        )

    if isinstance(node, ra.NaturalJoin):
        return OperatorTreeNode(
            id=nid,
            label="⋈",
            operator="natural_join",
            children=[
                build_operator_tree(node.left, ids),
                build_operator_tree(node.right, ids),
            ],
        )

    if isinstance(node, ra.ThetaJoin):
        return OperatorTreeNode(
            id=nid,
            label=f"⋈ {_fmt_expr(node.condition)}",
            operator="theta_join",
            children=[
                build_operator_tree(node.left, ids),
                build_operator_tree(node.right, ids),
            ],
        )

    return OperatorTreeNode(id=nid, label="?", operator="unknown", children=[])
