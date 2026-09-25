from __future__ import annotations

from pathlib import Path

from lark import Lark, Transformer, Token, v_args
from lark.exceptions import LarkError

from app.parsers.relalg import ast as ra


class RelAlgParseError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _unquote(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1].replace("\\" + s[0], s[0])
    return s


@v_args(inline=True)
class RelAlgTransformer(Transformer):
    def relation(self, name: Token) -> ra.Relation:
        return ra.Relation(name=str(name))

    def projection(self, _op: Token, proj_list: list, child: ra.RANode) -> ra.Projection:
        return ra.Projection(items=proj_list, child=child)

    def proj_list(self, *items: tuple) -> list:
        return list(items)

    def proj_item(self, expr: object, alias: Token | None = None) -> tuple:
        return (expr, str(alias) if alias is not None else None)

    def selection(self, _op: Token, condition: object, child: ra.RANode) -> ra.Selection:
        return ra.Selection(condition=condition, child=child)

    def rename(self, _op: Token, target: object, child: ra.RANode) -> ra.RANode:
        if isinstance(target, str):
            return ra.RenameRelation(new_name=target, child=child)
        return ra.RenameColumns(mapping=target, child=child)

    def rename_relation(self, name: Token) -> str:
        return str(name)

    def rename_columns_wrap(self, cols: list) -> list:
        return cols

    def rename_cols(self, *cols: tuple[str, str]) -> list:
        return list(cols)

    def rename_col(self, old: Token, _arrow: Token, new: Token) -> tuple[str, str]:
        return (str(old), str(new))

    def union(self, left: ra.RANode, _op: Token, right: ra.RANode) -> ra.Union:
        return ra.Union(left=left, right=right)

    def intersect(self, left: ra.RANode, _op: Token, right: ra.RANode) -> ra.Intersect:
        return ra.Intersect(left=left, right=right)

    def difference(self, left: ra.RANode, _op: Token, right: ra.RANode) -> ra.Except:
        return ra.Except(left=left, right=right)

    def cross(self, left: ra.RANode, _op: Token, right: ra.RANode) -> ra.Cross:
        return ra.Cross(left=left, right=right)

    def join(self, left: ra.RANode, _op: Token, right: ra.RANode, on=None) -> ra.RANode:
        if on is None:
            return ra.NaturalJoin(left=left, right=right)
        return ra.ThetaJoin(left=left, right=right, condition=on)

    def join_on(self, _on: Token, condition: object) -> object:
        return condition

    def comparison(self, left: object, op: Token, right: object) -> ra.BinaryExpr:
        return ra.BinaryExpr(op=str(op), left=left, right=right)

    def and_expr(self, left: object, _op: Token, right: object) -> ra.BinaryExpr:
        return ra.BinaryExpr(op="and", left=left, right=right)

    def or_expr(self, left: object, _op: Token, right: object) -> ra.BinaryExpr:
        return ra.BinaryExpr(op="or", left=left, right=right)

    def not_expr(self, _op: Token, operand: object) -> ra.UnaryExpr:
        return ra.UnaryExpr(op="not", operand=operand)

    def add(self, left: object, _op: Token, right: object) -> ra.BinaryExpr:
        return ra.BinaryExpr(op="+", left=left, right=right)

    def sub(self, left: object, _op: Token, right: object) -> ra.BinaryExpr:
        return ra.BinaryExpr(op="-", left=left, right=right)

    def mul(self, left: object, _op: Token, right: object) -> ra.BinaryExpr:
        return ra.BinaryExpr(op="*", left=left, right=right)

    def div(self, left: object, _op: Token, right: object) -> ra.BinaryExpr:
        return ra.BinaryExpr(op="/", left=left, right=right)

    def number(self, tok: Token) -> ra.Literal:
        text = str(tok)
        value: int | float = float(text) if "." in text else int(text)
        return ra.Literal(value=value)

    def string(self, tok: Token) -> ra.Literal:
        return ra.Literal(value=_unquote(str(tok)))

    def null(self, _tok: Token) -> ra.Literal:
        return ra.Literal(value=None)

    def column(self, name: Token) -> ra.ColumnRef:
        return ra.ColumnRef(name=str(name))

    def qualified_column(self, relation: Token, name: Token) -> ra.ColumnRef:
        return ra.ColumnRef(name=str(name), relation=str(relation))


_GRAMMAR_PATH = Path(__file__).with_name("grammar.lark")
_PARSER = Lark(
    _GRAMMAR_PATH.read_text(encoding="utf-8"),
    start="start",
    parser="lalr",
    propagate_positions=True,
)


def parse_relalg(query: str) -> ra.RANode:
    try:
        tree = _PARSER.parse(query.strip())
        result = RelAlgTransformer().transform(tree)
        if not isinstance(result, ra.RANode):
            raise RelAlgParseError("Invalid RelAlg expression")
        return result
    except LarkError as exc:
        raise RelAlgParseError(str(exc)) from exc
