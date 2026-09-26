from __future__ import annotations

from app.parsers.relalg import ast as ra


class CompileError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise CompileError(f"Unsupported literal: {value!r}")


def _is_null_literal(node: object) -> bool:
    return isinstance(node, ra.Literal) and node.value is None


def _sql_null_comparison(op: str, left: object, right: object) -> str | None:
    """Rewrite ``expr = null`` / ``expr != null`` to ``IS [NOT] NULL``.

    SQL three-valued logic makes ``col = NULL`` never true; RelAlg (and RelaX)
    treat equality with the null literal as an is-null test. Works for any
    column type.
    """
    left_null = _is_null_literal(left)
    right_null = _is_null_literal(right)
    if not left_null and not right_null:
        return None
    if op in ("=", "=="):
        is_null = True
    elif op in ("!=", "<>"):
        is_null = False
    else:
        # Other comparisons with null stay as-is (always unknown in SQL).
        return None
    if left_null and right_null:
        # null = null → true; null != null → false
        return "(TRUE)" if is_null else "(FALSE)"
    other = right if left_null else left
    keyword = "IS NULL" if is_null else "IS NOT NULL"
    return f"({_sql_expr(other)} {keyword})"


def _sql_expr(node: object) -> str:
    if isinstance(node, ra.ColumnRef):
        if node.name == "*":
            return "*"
        if node.relation:
            return f"{_quote_ident(node.relation)}.{_quote_ident(node.name)}"
        return _quote_ident(node.name)
    if isinstance(node, ra.Literal):
        return _sql_literal(node.value)
    if isinstance(node, ra.CaseExpr):
        parts = ["CASE"]
        for cond, result in node.whens:
            parts.append(f"WHEN {_sql_expr(cond)} THEN {_sql_expr(result)}")
        if node.else_result is not None:
            parts.append(f"ELSE {_sql_expr(node.else_result)}")
        parts.append("END")
        return "(" + " ".join(parts) + ")"
    if isinstance(node, ra.FuncCall):
        return _sql_func(node)
    if isinstance(node, ra.BinaryExpr):
        op = node.op
        if op == "<>":
            op = "!="
        null_cmp = _sql_null_comparison(op, node.left, node.right)
        if null_cmp is not None:
            return null_cmp
        if op == "xor":
            return (
                f"(({_sql_expr(node.left)}) <> ({_sql_expr(node.right)}))"
            )
        if op in ("and", "or"):
            return f"({_sql_expr(node.left)} {op.upper()} {_sql_expr(node.right)})"
        if op in ("like", "ilike"):
            return f"({_sql_expr(node.left)} {op.upper()} {_sql_expr(node.right)})"
        if op == "%":
            return f"({_sql_expr(node.left)} % {_sql_expr(node.right)})"
        return f"({_sql_expr(node.left)} {op} {_sql_expr(node.right)})"
    if isinstance(node, ra.UnaryExpr):
        if node.op == "not":
            return f"(NOT {_sql_expr(node.operand)})"
        raise CompileError(f"Unsupported unary op: {node.op}")
    if node == "*":
        return "*"
    raise CompileError(f"Unsupported expression: {node!r}")


def _expr_contains_rownum(node: object) -> bool:
    if isinstance(node, ra.FuncCall) and node.name.lower() in ("rownum", "row_number"):
        return True
    if isinstance(node, ra.CaseExpr):
        for cond, result in node.whens:
            if _expr_contains_rownum(cond) or _expr_contains_rownum(result):
                return True
        return node.else_result is not None and _expr_contains_rownum(node.else_result)
    if isinstance(node, ra.BinaryExpr):
        return _expr_contains_rownum(node.left) or _expr_contains_rownum(node.right)
    if isinstance(node, ra.UnaryExpr):
        return _expr_contains_rownum(node.operand)
    if isinstance(node, ra.FuncCall):
        return any(_expr_contains_rownum(a) for a in node.args)
    return False


def _sql_func(node: ra.FuncCall) -> str:
    name = node.name.lower()
    args = node.args

    def a(i: int = 0) -> str:
        if i >= len(args):
            raise CompileError(f"{name}() expects more arguments")
        return _sql_expr(args[i])

    # Nullary / special
    if name in ("rownum", "row_number"):
        if args:
            raise CompileError("rownum() takes no arguments")
        return "((ROW_NUMBER() OVER ()) - 1)"
    if name == "rand":
        if args:
            raise CompileError("rand() takes no arguments")
        return "random()"
    if name in ("now", "transaction_timestamp", "statement_timestamp", "clock_timestamp"):
        if args:
            raise CompileError(f"{name}() takes no arguments")
        return "CURRENT_TIMESTAMP"

    # String
    if name in ("length", "strlen"):
        return f"LENGTH(CAST({a(0)} AS VARCHAR))"
    if name in ("upper", "ucase"):
        return f"UPPER(CAST({a(0)} AS VARCHAR))"
    if name in ("lower", "lcase"):
        return f"LOWER(CAST({a(0)} AS VARCHAR))"
    if name == "concat":
        if not args:
            raise CompileError("concat() needs at least one argument")
        return "CONCAT(" + ", ".join(
            f"CAST({_sql_expr(x)} AS VARCHAR)" for x in args
        ) + ")"

    # Date / time
    if name == "date":
        return f"CAST({a(0)} AS DATE)"
    if name == "adddate":
        return f"(({a(0)})::DATE + CAST({a(1)} AS INTEGER) * INTERVAL 1 DAY)"
    if name == "subdate":
        return f"(({a(0)})::DATE - CAST({a(1)} AS INTEGER) * INTERVAL 1 DAY)"
    if name == "year":
        return f"EXTRACT(YEAR FROM CAST({a(0)} AS TIMESTAMP))"
    if name == "month":
        return f"EXTRACT(MONTH FROM CAST({a(0)} AS TIMESTAMP))"
    if name in ("day", "dayofmonth"):
        return f"EXTRACT(DAY FROM CAST({a(0)} AS TIMESTAMP))"
    if name == "hour":
        return f"EXTRACT(HOUR FROM CAST({a(0)} AS TIMESTAMP))"
    if name == "minute":
        return f"EXTRACT(MINUTE FROM CAST({a(0)} AS TIMESTAMP))"
    if name == "second":
        return f"EXTRACT(SECOND FROM CAST({a(0)} AS TIMESTAMP))"

    # Numeric
    if name == "abs":
        return f"ABS({a(0)})"
    if name == "round":
        return f"ROUND({a(0)})" if len(args) == 1 else f"ROUND({a(0)}, {a(1)})"
    if name == "floor":
        return f"FLOOR({a(0)})"
    if name in ("ceil", "ceiling"):
        return f"CEIL({a(0)})"
    if name == "add":
        return f"({a(0)} + {a(1)})"
    if name == "sub":
        return f"({a(0)} - {a(1)})"
    if name == "mul":
        return f"({a(0)} * {a(1)})"
    if name == "div":
        return f"({a(0)} / {a(1)})"
    if name == "mod":
        return f"({a(0)} % {a(1)})"

    # Misc
    if name == "coalesce":
        if not args:
            raise CompileError("coalesce() needs at least one argument")
        return "COALESCE(" + ", ".join(_sql_expr(x) for x in args) + ")"

    # Pass-through aggregates / unknown SQL-like names
    rendered_args = ", ".join(
        "*" if isinstance(x, ra.ColumnRef) and x.name == "*" else _sql_expr(x)
        for x in args
    )
    return f"{name.upper()}({rendered_args})"


def _unqualify_columns(node: object) -> object:
    """Drop Relation. prefixes — nested subqueries only expose flat column names."""
    if isinstance(node, ra.ColumnRef) and node.relation:
        return ra.ColumnRef(name=node.name, relation=None)
    if isinstance(node, ra.BinaryExpr):
        return ra.BinaryExpr(
            op=node.op,
            left=_unqualify_columns(node.left),
            right=_unqualify_columns(node.right),
        )
    if isinstance(node, ra.UnaryExpr):
        return ra.UnaryExpr(op=node.op, operand=_unqualify_columns(node.operand))
    if isinstance(node, ra.FuncCall):
        return ra.FuncCall(
            name=node.name,
            args=[_unqualify_columns(a) for a in node.args],
        )
    if isinstance(node, ra.CaseExpr):
        return ra.CaseExpr(
            whens=[
                (_unqualify_columns(c), _unqualify_columns(r)) for c, r in node.whens
            ],
            else_result=(
                _unqualify_columns(node.else_result)
                if node.else_result is not None
                else None
            ),
        )
    return node


def _relation_names_in(node: ra.RANode) -> set[str]:
    """Base / renamed relation names visible in a RelAlg subtree."""
    if isinstance(node, ra.Relation):
        return {node.name}
    if isinstance(node, ra.RenameRelation):
        return {node.new_name}
    if isinstance(node, ra.Statement):
        return _relation_names_in(node.result)
    names: set[str] = set()
    for attr in ("child", "left", "right"):
        child = getattr(node, attr, None)
        if isinstance(child, ra.RANode):
            names |= _relation_names_in(child)
    return names


def _rewrite_join_expr(
    node: object,
    left_names: set[str],
    right_names: set[str],
    la: str,
    ra_alias: str,
) -> object:
    """Rewrite R.col / S.col in join predicates to subquery aliases."""
    if isinstance(node, ra.ColumnRef) and node.relation:
        if node.relation in left_names and node.relation not in right_names:
            return ra.ColumnRef(name=node.name, relation=la)
        if node.relation in right_names and node.relation not in left_names:
            return ra.ColumnRef(name=node.name, relation=ra_alias)
        if node.relation in left_names:
            return ra.ColumnRef(name=node.name, relation=la)
        if node.relation in right_names:
            return ra.ColumnRef(name=node.name, relation=ra_alias)
        # Unknown qualifier — leave bare so DuckDB can resolve by column name
        return ra.ColumnRef(name=node.name, relation=None)
    if isinstance(node, ra.BinaryExpr):
        return ra.BinaryExpr(
            op=node.op,
            left=_rewrite_join_expr(node.left, left_names, right_names, la, ra_alias),
            right=_rewrite_join_expr(node.right, left_names, right_names, la, ra_alias),
        )
    if isinstance(node, ra.UnaryExpr):
        return ra.UnaryExpr(
            op=node.op,
            operand=_rewrite_join_expr(
                node.operand, left_names, right_names, la, ra_alias
            ),
        )
    if isinstance(node, ra.FuncCall):
        return ra.FuncCall(
            name=node.name,
            args=[
                _rewrite_join_expr(a, left_names, right_names, la, ra_alias)
                for a in node.args
            ],
        )
    if isinstance(node, ra.CaseExpr):
        return ra.CaseExpr(
            whens=[
                (
                    _rewrite_join_expr(c, left_names, right_names, la, ra_alias),
                    _rewrite_join_expr(r, left_names, right_names, la, ra_alias),
                )
                for c, r in node.whens
            ],
            else_result=(
                _rewrite_join_expr(
                    node.else_result, left_names, right_names, la, ra_alias
                )
                if node.else_result is not None
                else None
            ),
        )
    return node


def _join_sql(
    left_sql: str,
    right_sql: str,
    la: str,
    ra_alias: str,
    join_type: str,
    condition: object | None,
    *,
    left_node: ra.RANode | None = None,
    right_node: ra.RANode | None = None,
) -> str:
    left = f"({left_sql}) AS {_quote_ident(la)}"
    right = f"({right_sql}) AS {_quote_ident(ra_alias)}"
    if condition is None:
        if join_type == "INNER":
            return f"SELECT * FROM {left} NATURAL JOIN {right}"
        return f"SELECT * FROM {left} NATURAL {join_type} JOIN {right}"
    left_names = _relation_names_in(left_node) if left_node is not None else set()
    right_names = _relation_names_in(right_node) if right_node is not None else set()
    rewritten = _rewrite_join_expr(condition, left_names, right_names, la, ra_alias)
    # Unqualified same-name equality: a = a → USING(a)
    if (
        isinstance(rewritten, ra.BinaryExpr)
        and rewritten.op == "="
        and isinstance(rewritten.left, ra.ColumnRef)
        and isinstance(rewritten.right, ra.ColumnRef)
        and rewritten.left.relation is None
        and rewritten.right.relation is None
        and rewritten.left.name == rewritten.right.name
    ):
        return (
            f"SELECT * FROM {left} {join_type} JOIN {right} "
            f"USING ({_quote_ident(rewritten.left.name)})"
        )
    cond = _sql_expr(rewritten)
    return f"SELECT * FROM {left} {join_type} JOIN {right} ON {cond}"


class SqlCompiler:
    def __init__(self) -> None:
        self._alias = 0

    def _next_alias(self, prefix: str = "t") -> str:
        self._alias += 1
        return f"{prefix}{self._alias}"

    def compile(self, node: ra.RANode) -> str:
        assignments: list[tuple[str, ra.RANode]] = []
        result = node
        if isinstance(node, ra.Statement):
            assignments = list(node.assignments or [])
            result = node.result
        else:
            assignments = list(getattr(node, "_assignments", None) or [])

        with_parts: list[str] = []
        for name, expr in assignments:
            with_parts.append(f"{_quote_ident(name)} AS ({self._compile(expr)})")
        body = self._compile(result)
        root = f"SELECT * FROM ({body}) AS {_quote_ident(self._next_alias('root'))}"
        if with_parts:
            return "WITH " + ", ".join(with_parts) + " " + root
        return root

    def _compile(self, node: ra.RANode) -> str:
        if isinstance(node, ra.Relation):
            return f"SELECT * FROM {_quote_ident(node.name)}"

        if isinstance(node, ra.Projection):
            child_sql = self._compile(node.child)
            alias = self._next_alias()
            if len(node.items) == 1 and isinstance(node.items[0][0], ra.ColumnRef) and node.items[0][0].name == "*":
                return f"SELECT DISTINCT * FROM ({child_sql}) AS {_quote_ident(alias)}"
            parts: list[str] = []
            for expr, col_alias in node.items:
                rendered = _sql_expr(_unqualify_columns(expr))
                if col_alias:
                    parts.append(f"{rendered} AS {_quote_ident(col_alias)}")
                else:
                    parts.append(rendered)
            select_list = ", ".join(parts) if parts else "*"
            return (
                f"SELECT DISTINCT {select_list} FROM ({child_sql}) AS {_quote_ident(alias)}"
            )

        if isinstance(node, ra.Selection):
            child_sql = self._compile(node.child)
            alias = self._next_alias()
            cond_node = _unqualify_columns(node.condition)
            cond = _sql_expr(cond_node)
            if _expr_contains_rownum(node.condition):
                # DuckDB QUALIFY allows window functions in filters.
                return (
                    f"SELECT * FROM ({child_sql}) AS {_quote_ident(alias)} "
                    f"QUALIFY {cond}"
                )
            return f"SELECT * FROM ({child_sql}) AS {_quote_ident(alias)} WHERE {cond}"

        if isinstance(node, ra.RenameRelation):
            child_sql = self._compile(node.child)
            return f"SELECT * FROM ({child_sql}) AS {_quote_ident(node.new_name)}"

        if isinstance(node, ra.RenameColumns):
            child_sql = self._compile(node.child)
            alias = self._next_alias()
            mapping = {old: new for old, new in node.mapping}
            exclude = ", ".join(_quote_ident(old) for old in mapping)
            renamed = ", ".join(
                f"{_quote_ident(old)} AS {_quote_ident(new)}" for old, new in mapping.items()
            )
            if exclude:
                return (
                    f"SELECT * EXCLUDE ({exclude}), {renamed} "
                    f"FROM ({child_sql}) AS {_quote_ident(alias)}"
                )
            return f"SELECT * FROM ({child_sql}) AS {_quote_ident(alias)}"

        if isinstance(node, ra.OrderBy):
            child_sql = self._compile(node.child)
            alias = self._next_alias()
            keys = ", ".join(
                f"{_sql_expr(_unqualify_columns(expr))} {direction.upper()}"
                for expr, direction in node.keys
            )
            return (
                f"SELECT * FROM ({child_sql}) AS {_quote_ident(alias)} ORDER BY {keys}"
            )

        if isinstance(node, ra.GroupBy):
            child_sql = self._compile(node.child)
            alias = self._next_alias()
            group_cols = [_sql_expr(_unqualify_columns(c)) for c in node.group_cols]
            select_parts = list(group_cols)
            for fn, arg, agg_alias in node.aggregates:
                rendered = f"{fn.upper()}({_sql_expr(_unqualify_columns(arg))})"
                if agg_alias:
                    rendered = f"{rendered} AS {_quote_ident(agg_alias)}"
                select_parts.append(rendered)
            if not select_parts:
                select_parts = ["*"]
            select_list = ", ".join(select_parts)
            sql = f"SELECT {select_list} FROM ({child_sql}) AS {_quote_ident(alias)}"
            if group_cols:
                sql += " GROUP BY " + ", ".join(group_cols)
            return sql

        if isinstance(node, ra.Distinct):
            child_sql = self._compile(node.child)
            alias = self._next_alias()
            return f"SELECT DISTINCT * FROM ({child_sql}) AS {_quote_ident(alias)}"

        if isinstance(node, ra.Union):
            return f"({self._compile(node.left)}) UNION ({self._compile(node.right)})"

        if isinstance(node, ra.Intersect):
            return (
                f"({self._compile(node.left)}) INTERSECT ({self._compile(node.right)})"
            )

        if isinstance(node, ra.Except):
            return f"({self._compile(node.left)}) EXCEPT ({self._compile(node.right)})"

        if isinstance(node, ra.Cross):
            left = self._compile(node.left)
            right = self._compile(node.right)
            la, ra_alias = self._next_alias("l"), self._next_alias("r")
            return (
                f"SELECT * FROM ({left}) AS {_quote_ident(la)} "
                f"CROSS JOIN ({right}) AS {_quote_ident(ra_alias)}"
            )

        if isinstance(node, ra.NaturalJoin):
            return _join_sql(
                self._compile(node.left),
                self._compile(node.right),
                self._next_alias("l"),
                self._next_alias("r"),
                "INNER",
                None,
            )

        if isinstance(node, ra.ThetaJoin):
            la, ra_alias = self._next_alias("l"), self._next_alias("r")
            return _join_sql(
                self._compile(node.left),
                self._compile(node.right),
                la,
                ra_alias,
                "INNER",
                node.condition,
                left_node=node.left,
                right_node=node.right,
            )

        if isinstance(node, ra.LeftOuterJoin):
            la, ra_alias = self._next_alias("l"), self._next_alias("r")
            return _join_sql(
                self._compile(node.left),
                self._compile(node.right),
                la,
                ra_alias,
                "LEFT",
                node.condition,
                left_node=node.left,
                right_node=node.right,
            )

        if isinstance(node, ra.RightOuterJoin):
            la, ra_alias = self._next_alias("l"), self._next_alias("r")
            return _join_sql(
                self._compile(node.left),
                self._compile(node.right),
                la,
                ra_alias,
                "RIGHT",
                node.condition,
                left_node=node.left,
                right_node=node.right,
            )

        if isinstance(node, ra.FullOuterJoin):
            la, ra_alias = self._next_alias("l"), self._next_alias("r")
            return _join_sql(
                self._compile(node.left),
                self._compile(node.right),
                la,
                ra_alias,
                "FULL",
                node.condition,
                left_node=node.left,
                right_node=node.right,
            )

        if isinstance(node, ra.LeftSemiJoin):
            left = self._compile(node.left)
            right = self._compile(node.right)
            la, ra_alias = self._next_alias("l"), self._next_alias("r")
            if node.condition is None:
                return (
                    f"SELECT DISTINCT {_quote_ident(la)}.* FROM ({left}) AS {_quote_ident(la)} "
                    f"SEMI JOIN ({right}) AS {_quote_ident(ra_alias)}"
                )
            rewritten = _rewrite_join_expr(
                node.condition,
                _relation_names_in(node.left),
                _relation_names_in(node.right),
                la,
                ra_alias,
            )
            cond = _sql_expr(rewritten)
            return (
                f"SELECT DISTINCT {_quote_ident(la)}.* FROM ({left}) AS {_quote_ident(la)} "
                f"SEMI JOIN ({right}) AS {_quote_ident(ra_alias)} ON {cond}"
            )

        if isinstance(node, ra.RightSemiJoin):
            # Emulate as left semi with sides swapped, projecting right columns
            left = self._compile(node.right)
            right = self._compile(node.left)
            la, ra_alias = self._next_alias("l"), self._next_alias("r")
            if node.condition is None:
                return (
                    f"SELECT DISTINCT {_quote_ident(la)}.* FROM ({left}) AS {_quote_ident(la)} "
                    f"SEMI JOIN ({right}) AS {_quote_ident(ra_alias)}"
                )
            rewritten = _rewrite_join_expr(
                node.condition,
                _relation_names_in(node.right),
                _relation_names_in(node.left),
                la,
                ra_alias,
            )
            cond = _sql_expr(rewritten)
            return (
                f"SELECT DISTINCT {_quote_ident(la)}.* FROM ({left}) AS {_quote_ident(la)} "
                f"SEMI JOIN ({right}) AS {_quote_ident(ra_alias)} ON {cond}"
            )

        if isinstance(node, ra.AntiJoin):
            left = self._compile(node.left)
            right = self._compile(node.right)
            la, ra_alias = self._next_alias("l"), self._next_alias("r")
            if node.condition is None:
                return (
                    f"SELECT {_quote_ident(la)}.* FROM ({left}) AS {_quote_ident(la)} "
                    f"ANTI JOIN ({right}) AS {_quote_ident(ra_alias)}"
                )
            rewritten = _rewrite_join_expr(
                node.condition,
                _relation_names_in(node.left),
                _relation_names_in(node.right),
                la,
                ra_alias,
            )
            cond = _sql_expr(rewritten)
            return (
                f"SELECT {_quote_ident(la)}.* FROM ({left}) AS {_quote_ident(la)} "
                f"ANTI JOIN ({right}) AS {_quote_ident(ra_alias)} ON {cond}"
            )

        if isinstance(node, ra.Division):
            # Handled specially in executor with schema introspection.
            raise CompileError("DIVISION_NEEDS_SCHEMA")

        raise CompileError(f"Unsupported RelAlg node: {type(node).__name__}")


def compile_relalg(node: ra.RANode) -> str:
    return SqlCompiler().compile(node)
