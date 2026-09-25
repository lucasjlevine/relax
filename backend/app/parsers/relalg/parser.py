from __future__ import annotations

from pathlib import Path

from lark import Lark, Transformer, Token, Tree, v_args
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


def _norm_compare(op: str) -> str:
    return {"≠": "!=", "≤": "<=", "≥": ">="}.get(op, op)


@v_args(inline=True)
class RelAlgTransformer(Transformer):
    def statement(self, *parts: object) -> ra.RANode:
        # assignments? expr — if assignments present, wrap via sequential renames not needed;
        # for MVP we only return the final expr (assignments executed as CTE-like in compiler later).
        if len(parts) == 1:
            return parts[0]  # type: ignore[return-value]
        assignments, expr = parts
        # Attach assignments metadata via a simple approach: store on a wrapper
        node = expr
        if isinstance(assignments, list) and assignments:
            # Represent as nested With-like by converting to Views in compiler via Attribute
            setattr(node, "_assignments", assignments)
        return node  # type: ignore[return-value]

    def assignments(self, *items: tuple[str, ra.RANode]) -> list:
        return list(items)

    def assignment(self, name: Token, expr: ra.RANode) -> tuple[str, ra.RANode]:
        return (str(name), expr)

    def relation(self, name: Token) -> ra.Relation:
        return ra.Relation(name=str(name))

    def projection(self, _op: Token, proj_args: list, child: ra.RANode) -> ra.Projection:
        return ra.Projection(items=proj_args, child=child)

    def proj_args(self, *args: object) -> list:
        # Either SUB_OPEN list SUB_CLOSE already reduced to list, or bare list
        for a in args:
            if isinstance(a, list):
                return a
        return []

    def proj_list(self, *items: object) -> list:
        return list(items)

    def proj_star(self, _star: Token) -> list:
        return [(ra.ColumnRef(name="*"), None)]

    def proj_item(self, expr: object, alias: str | None = None) -> tuple:
        return (expr, alias)

    def proj_alias(self, _arrow: Token, name: Token) -> str:
        return str(name)

    def selection(self, _op: Token, sel_args: object, child: ra.RANode) -> ra.Selection:
        return ra.Selection(condition=sel_args, child=child)

    def sel_args(self, *args: object) -> object:
        for a in args:
            if not isinstance(a, Token):
                return a
        raise RelAlgParseError("Missing selection condition")

    def rename(self, _op: Token, rename_args: object, child: ra.RANode) -> ra.RANode:
        target = rename_args
        if isinstance(target, str):
            return ra.RenameRelation(new_name=target, child=child)
        return ra.RenameColumns(mapping=target, child=child)  # type: ignore[arg-type]

    def rename_args(self, *args: object) -> object:
        for a in args:
            if not isinstance(a, Token):
                return a
        raise RelAlgParseError("Missing rename target")

    def rename_relation(self, name: Token) -> str:
        return str(name)

    def rename_columns_wrap(self, cols: list) -> list:
        return cols

    def rename_cols(self, *cols: tuple[str, str]) -> list:
        return list(cols)

    def rename_col(self, old: Token, _arrow: Token, new: Token) -> tuple[str, str]:
        return (str(old), str(new))

    def orderby(self, _op: Token, order_args: list, child: ra.RANode) -> ra.OrderBy:
        return ra.OrderBy(keys=order_args, child=child)

    def order_args(self, *args: object) -> list:
        for a in args:
            if isinstance(a, list):
                return a
        return []

    def order_list(self, *items: tuple) -> list:
        return list(items)

    def order_item(self, expr: object, direction: str | None = None) -> tuple:
        return (expr, direction or "asc")

    def order_dir(self, direction: Token) -> str:
        return "desc" if str(direction).lower() == "desc" else "asc"

    def groupby(self, _op: Token, group_args: tuple, child: ra.RANode) -> ra.GroupBy:
        group_cols, aggregates = group_args
        return ra.GroupBy(group_cols=group_cols, aggregates=aggregates, child=child)

    def group_args(self, *args: object) -> tuple:
        for a in args:
            if isinstance(a, tuple) and len(a) == 2:
                return a  # type: ignore[return-value]
        raise RelAlgParseError("Invalid group by")

    def group_spec(self, group_cols: list, agg_list: list | None = None) -> tuple:
        return (group_cols, agg_list or [])

    def group_aggs_only(self, agg_list: list) -> tuple:
        return ([], agg_list)

    def group_cols(self, *cols: object) -> list:
        return list(cols)

    def agg_list(self, *items: tuple) -> list:
        return list(items)

    def agg_item(self, fn: Token, arg: object, alias: str | None = None) -> tuple:
        return (str(fn).lower(), arg, alias)

    def agg_alias(self, _arrow: Token, name: Token) -> str:
        return str(name)

    def agg_arg(self, arg: object) -> object:
        if isinstance(arg, Token) and str(arg) == "*":
            return ra.ColumnRef(name="*")
        return arg

    def distinct(self, _op: Token, child: ra.RANode) -> ra.Distinct:
        return ra.Distinct(child=child)

    def union(self, left: ra.RANode, _op: Token, right: ra.RANode) -> ra.Union:
        return ra.Union(left=left, right=right)

    def intersect(self, left: ra.RANode, _op: Token, right: ra.RANode) -> ra.Intersect:
        return ra.Intersect(left=left, right=right)

    def difference(self, left: ra.RANode, _op: Token, right: ra.RANode) -> ra.Except:
        return ra.Except(left=left, right=right)

    def division(self, left: ra.RANode, _op: Token, right: ra.RANode) -> ra.Division:
        return ra.Division(left=left, right=right)

    def cross(self, left: ra.RANode, _op: Token, right: ra.RANode) -> ra.Cross:
        return ra.Cross(left=left, right=right)

    def join_kind(
        self,
        left: ra.RANode,
        kind: Token,
        right: ra.RANode,
        on: object | None = None,
    ) -> ra.RANode:
        k = str(kind).lower().replace(" ", "")
        symbol = str(kind)
        if symbol in ("⋈",) or k == "join":
            if on is None:
                return ra.NaturalJoin(left=left, right=right)
            return ra.ThetaJoin(left=left, right=right, condition=on)
        if symbol in ("⟕",) or "leftouter" in k or k in ("leftjoin", "leftouterjoin"):
            return ra.LeftOuterJoin(left=left, right=right, condition=on)
        if symbol in ("⟖",) or "rightouter" in k or k in ("rightjoin", "rightouterjoin"):
            return ra.RightOuterJoin(left=left, right=right, condition=on)
        if symbol in ("⟗",) or "fullouter" in k or k in ("fulljoin", "fullouterjoin"):
            return ra.FullOuterJoin(left=left, right=right, condition=on)
        if symbol in ("⋉",) or "semi" in k:
            if "right" in k:
                return ra.RightSemiJoin(left=left, right=right, condition=on)
            return ra.LeftSemiJoin(left=left, right=right, condition=on)
        if symbol in ("▷",) or "anti" in k:
            return ra.AntiJoin(left=left, right=right, condition=on)
        if on is None:
            return ra.NaturalJoin(left=left, right=right)
        return ra.ThetaJoin(left=left, right=right, condition=on)

    def join_on(self, *args: object) -> object:
        for a in args:
            if not isinstance(a, Token):
                return a
        raise RelAlgParseError("Missing join condition")

    def comparison(self, left: object, op: Token, right: object) -> ra.BinaryExpr:
        return ra.BinaryExpr(op=_norm_compare(str(op)), left=left, right=right)

    def like_expr(self, left: object, op: Token, right: object) -> ra.BinaryExpr:
        return ra.BinaryExpr(op=str(op).lower(), left=left, right=right)

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

    def func_call(self, name: Token, args: list | None = None) -> ra.FuncCall:
        return ra.FuncCall(name=str(name).lower(), args=list(args or []))

    def func_call_agg(self, name: Token, arg: object) -> ra.FuncCall:
        return ra.FuncCall(name=str(name).lower(), args=[arg])

    def expr_list(self, *items: object) -> list:
        return list(items)


_GRAMMAR_PATH = Path(__file__).with_name("grammar.lark")


_PARSER = Lark(
    _GRAMMAR_PATH.read_text(encoding="utf-8"),
    start="start",
    parser="earley",
    ambiguity="resolve",
    propagate_positions=True,
)


def parse_relalg(query: str) -> ra.RANode:
    try:
        tree = _PARSER.parse(query.strip())
        result = RelAlgTransformer().transform(tree)
        if isinstance(result, Tree):
            raise RelAlgParseError("Invalid RelAlg expression")
        if not isinstance(result, ra.RANode):
            raise RelAlgParseError("Invalid RelAlg expression")
        return result
    except LarkError as exc:
        raise RelAlgParseError(str(exc)) from exc
    except RelAlgParseError:
        raise
    except Exception as exc:  # transformer errors
        raise RelAlgParseError(str(exc)) from exc
