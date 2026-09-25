from __future__ import annotations

from dataclasses import dataclass
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
    items: list[tuple[Any, str | None]]
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
    mapping: list[tuple[str, str]]
    child: RANode


@dataclass
class OrderBy(RANode):
    keys: list[tuple[Any, str]]  # (expr, "asc"|"desc")
    child: RANode


@dataclass
class GroupBy(RANode):
    group_cols: list[Any]
    aggregates: list[tuple[str, Any, str | None]]  # (fn, expr, alias)
    child: RANode


@dataclass
class Distinct(RANode):
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


@dataclass
class LeftOuterJoin(BinaryOp):
    condition: Any | None = None  # None => natural


@dataclass
class RightOuterJoin(BinaryOp):
    condition: Any | None = None


@dataclass
class FullOuterJoin(BinaryOp):
    condition: Any | None = None


@dataclass
class LeftSemiJoin(BinaryOp):
    condition: Any | None = None


@dataclass
class RightSemiJoin(BinaryOp):
    condition: Any | None = None


@dataclass
class AntiJoin(BinaryOp):
    condition: Any | None = None


@dataclass
class Division(BinaryOp):
    pass


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


@dataclass
class FuncCall:
    name: str
    args: list[Any]
