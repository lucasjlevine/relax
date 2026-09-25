from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RANode:
    """Base RelAlg AST node."""

    def op_name(self) -> str:
        return self.__class__.__name__


@dataclass
class Relation(RANode):
    name: str


@dataclass
class Projection(RANode):
    items: list[tuple[Any, str | None]]  # (expr, optional alias)
    child: RANode


@dataclass
class Selection(RANode):
    condition: Any
    child: RANode


@dataclass
class RenameRelation(RANode):
    new_name: str
    child: RANode


@dataclass
class RenameColumns(RANode):
    mapping: list[tuple[str, str]]  # (old, new)
    child: RANode


@dataclass
class BinaryOp(RANode):
    left: RANode
    right: RANode


@dataclass
class Union(BinaryOp):
    pass


@dataclass
class Intersect(BinaryOp):
    pass


@dataclass
class Except(BinaryOp):
    pass


@dataclass
class Cross(BinaryOp):
    pass


@dataclass
class NaturalJoin(BinaryOp):
    pass


@dataclass
class ThetaJoin(BinaryOp):
    condition: Any


# Value / condition expressions


@dataclass
class ColumnRef:
    name: str
    relation: str | None = None


@dataclass
class Literal:
    value: Any


@dataclass
class BinaryExpr:
    op: str
    left: Any
    right: Any


@dataclass
class UnaryExpr:
    op: str
    operand: Any
