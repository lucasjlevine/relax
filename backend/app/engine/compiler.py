from __future__ import annotations

from dataclasses import dataclass

from app.parsers.relalg import ast as ra


class CompileError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


@dataclass(frozen=True)
class ColBind:
    """One output column and which RelAlg ``Relation.attr`` origins it carries."""

    name: str
    origins: frozenset[tuple[str, str]]


def _unique_join_name(base: str, used: set[str]) -> str:
    """Pick an unused column name: ``base``, ``base_1``, ``base_2``, …"""
    if base not in used:
        return base
    i = 1
    while f"{base}_{i}" in used:
        i += 1
    return f"{base}_{i}"


def _relation_attr_alias(col: ColBind) -> str:
    """Stable alias ``Relation_attr`` for a column with known provenance."""
    if col.origins:
        rel, attr = sorted(col.origins)[0]
        return f"{rel}_{attr}"
    return col.name


def _schema_join_on(left: list[ColBind], right: list[ColBind]) -> list[ColBind]:
    """Schema after an ON/CROSS join: colliding right columns become ``Relation_attr``."""
    used = {c.name for c in left}
    out = list(left)
    for c in right:
        if c.name not in used:
            out.append(c)
            used.add(c.name)
        else:
            name = _unique_join_name(_relation_attr_alias(c), used)
            out.append(ColBind(name, c.origins))
            used.add(name)
    return out


def _join_on_select_list(
    left_schema: list[ColBind],
    right_schema: list[ColBind],
    la: str,
    ra_alias: str,
) -> str:
    """Explicit SELECT list matching ``_schema_join_on`` naming."""
    out_schema = _schema_join_on(left_schema, right_schema)
    parts: list[str] = []
    for i, c in enumerate(left_schema):
        parts.append(
            f"{_quote_ident(la)}.{_quote_ident(c.name)} AS {_quote_ident(out_schema[i].name)}"
        )
    offset = len(left_schema)
    for i, c in enumerate(right_schema):
        out = out_schema[offset + i]
        parts.append(
            f"{_quote_ident(ra_alias)}.{_quote_ident(c.name)} AS {_quote_ident(out.name)}"
        )
    return ", ".join(parts)


def _schema_natural(left: list[ColBind], right: list[ColBind]) -> list[ColBind]:
    """Schema after NATURAL JOIN / JOIN USING (shared names once)."""
    right_by = {c.name: c for c in right}
    out: list[ColBind] = []
    for c in left:
        if c.name in right_by:
            out.append(ColBind(c.name, c.origins | right_by[c.name].origins))
        else:
            out.append(c)
    left_names = {c.name for c in left}
    for c in right:
        if c.name not in left_names:
            out.append(c)
    return out


def _resolve_column(ref: ra.ColumnRef, schema: list[ColBind]) -> ra.ColumnRef:
    if ref.name == "*":
        return ref
    if ref.relation:
        matches = [c for c in schema if (ref.relation, ref.name) in c.origins]
        if matches:
            # Prefer the last match if duplicates (rightmost join wins) — should be 1.
            return ra.ColumnRef(name=matches[-1].name, relation=None)
        # Qualifier unknown in this subtree — fall back to bare name.
        return ra.ColumnRef(name=ref.name, relation=None)
    return ra.ColumnRef(name=ref.name, relation=None)


def _resolve_expr(node: object, schema: list[ColBind]) -> object:
    if isinstance(node, ra.ColumnRef):
        return _resolve_column(node, schema)
    if isinstance(node, ra.BinaryExpr):
        return ra.BinaryExpr(
            op=node.op,
            left=_resolve_expr(node.left, schema),
            right=_resolve_expr(node.right, schema),
        )
    if isinstance(node, ra.UnaryExpr):
        return ra.UnaryExpr(op=node.op, operand=_resolve_expr(node.operand, schema))
    if isinstance(node, ra.FuncCall):
        return ra.FuncCall(
            name=node.name,
            args=[_resolve_expr(a, schema) for a in node.args],
        )
    if isinstance(node, ra.CaseExpr):
        return ra.CaseExpr(
            whens=[
                (_resolve_expr(c, schema), _resolve_expr(r, schema))
                for c, r in node.whens
            ],
            else_result=(
                _resolve_expr(node.else_result, schema)
                if node.else_result is not None
                else None
            ),
        )
    return node


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
    left_schema: list[ColBind] | None = None,
    right_schema: list[ColBind] | None = None,
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
    if left_schema and right_schema:
        select_list = _join_on_select_list(left_schema, right_schema, la, ra_alias)
        return (
            f"SELECT {select_list} FROM {left} {join_type} JOIN {right} ON {cond}"
        )
    return f"SELECT * FROM {left} {join_type} JOIN {right} ON {cond}"


class SqlCompiler:
    def __init__(
        self, relation_columns: dict[str, list[str]] | None = None
    ) -> None:
        self._alias = 0
        # Base relation → attribute names (enables Relation.attr provenance)
        self._relation_columns = relation_columns or {}
        # CTE / assignment name → schema of that subquery
        self._cte_schemas: dict[str, list[ColBind]] = {}

    def _next_alias(self, prefix: str = "t") -> str:
        self._alias += 1
        return f"{prefix}{self._alias}"

    def _schema(self, node: ra.RANode) -> list[ColBind]:
        """Output column bindings for a RelAlg subtree."""
        if isinstance(node, ra.Statement):
            return self._schema(node.result)
        if isinstance(node, ra.Relation):
            if node.name in self._cte_schemas:
                return list(self._cte_schemas[node.name])
            cols = self._relation_columns.get(node.name)
            if not cols:
                return []
            return [
                ColBind(c, frozenset({(node.name, c)})) for c in cols
            ]
        if isinstance(node, ra.Selection):
            return self._schema(node.child)
        if isinstance(node, ra.Distinct):
            return self._schema(node.child)
        if isinstance(node, ra.OrderBy):
            return self._schema(node.child)
        if isinstance(node, ra.RenameRelation):
            child = self._schema(node.child)
            return [
                ColBind(c.name, frozenset({(node.new_name, c.name)})) for c in child
            ]
        if isinstance(node, ra.RenameColumns):
            mapping = {old: new for old, new in node.mapping}
            out: list[ColBind] = []
            for c in self._schema(node.child):
                new_name = mapping.get(c.name, c.name)
                origins = frozenset(
                    (rel, mapping.get(attr, attr) if attr == c.name else attr)
                    for rel, attr in c.origins
                )
                # Also bind (rel, new_name) for renamed attrs from each origin rel
                extra = set(origins)
                for rel, attr in c.origins:
                    if attr == c.name and new_name != c.name:
                        extra.add((rel, new_name))
                out.append(ColBind(new_name, frozenset(extra)))
            return out
        if isinstance(node, ra.Projection):
            child_schema = self._schema(node.child)
            if (
                len(node.items) == 1
                and isinstance(node.items[0][0], ra.ColumnRef)
                and node.items[0][0].name == "*"
            ):
                return child_schema
            out = []
            for expr, col_alias in node.items:
                resolved = _resolve_expr(expr, child_schema) if child_schema else expr
                if isinstance(resolved, ra.ColumnRef) and resolved.name != "*":
                    origins = next(
                        (c.origins for c in child_schema if c.name == resolved.name),
                        frozenset(),
                    )
                    name = col_alias or resolved.name
                    if col_alias and isinstance(expr, ra.ColumnRef) and expr.relation:
                        origins = origins | frozenset({(expr.relation, expr.name)})
                    out.append(ColBind(name, origins))
                else:
                    name = col_alias or "col"
                    out.append(ColBind(name, frozenset()))
            return out
        if isinstance(node, ra.GroupBy):
            child_schema = self._schema(node.child)
            out: list[ColBind] = []
            for c in node.group_cols:
                resolved = (
                    _resolve_expr(c, child_schema) if child_schema else c
                )
                if isinstance(resolved, ra.ColumnRef):
                    origins = next(
                        (b.origins for b in child_schema if b.name == resolved.name),
                        frozenset(),
                    )
                    out.append(ColBind(resolved.name, origins))
                else:
                    out.append(ColBind("col", frozenset()))
            for fn, arg, agg_alias in node.aggregates:
                name = agg_alias or f"{fn}"
                out.append(ColBind(name, frozenset()))
            return out
        if isinstance(node, (ra.Union, ra.Intersect, ra.Except)):
            return self._schema(node.left)
        if isinstance(node, ra.Cross):
            return _schema_join_on(self._schema(node.left), self._schema(node.right))
        if isinstance(node, ra.NaturalJoin):
            return _schema_natural(self._schema(node.left), self._schema(node.right))
        if isinstance(
            node,
            (
                ra.ThetaJoin,
                ra.LeftOuterJoin,
                ra.RightOuterJoin,
                ra.FullOuterJoin,
            ),
        ):
            left_s = self._schema(node.left)
            right_s = self._schema(node.right)
            # USING(a) when unqualified a = a — same shape as natural for that key
            cond = getattr(node, "condition", None)
            if (
                isinstance(cond, ra.BinaryExpr)
                and cond.op == "="
                and isinstance(cond.left, ra.ColumnRef)
                and isinstance(cond.right, ra.ColumnRef)
                and cond.left.relation is None
                and cond.right.relation is None
                and cond.left.name == cond.right.name
            ):
                return _schema_natural(left_s, right_s)
            return _schema_join_on(left_s, right_s)
        if isinstance(node, (ra.LeftSemiJoin, ra.AntiJoin)):
            return self._schema(node.left)
        if isinstance(node, ra.RightSemiJoin):
            return self._schema(node.right)
        if isinstance(node, ra.Division):
            # Quotient = left attrs − right attrs (approximation without running SQL)
            left_s = self._schema(node.left)
            right_names = {c.name for c in self._schema(node.right)}
            return [c for c in left_s if c.name not in right_names]
        if hasattr(node, "child") and isinstance(getattr(node, "child"), ra.RANode):
            return self._schema(node.child)
        return []

    def _bind_expr(self, expr: object, child: ra.RANode) -> object:
        """Map ``Relation.attr`` to the correct flat SQL column in ``child``'s result."""
        if not self._relation_columns and not self._cte_schemas:
            return _unqualify_columns(expr)
        schema = self._schema(child)
        if not schema:
            return _unqualify_columns(expr)
        return _resolve_expr(expr, schema)

    def compile(self, node: ra.RANode) -> str:
        assignments: list[tuple[str, ra.RANode]] = []
        result = node
        if isinstance(node, ra.Statement):
            assignments = list(node.assignments or [])
            result = node.result
        else:
            assignments = list(getattr(node, "_assignments", None) or [])

        with_parts: list[str] = []
        self._cte_schemas = {}
        for name, expr in assignments:
            self._cte_schemas[name] = self._schema(expr)
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
                rendered = _sql_expr(self._bind_expr(expr, node.child))
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
            cond_node = self._bind_expr(node.condition, node.child)
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
                f"{_sql_expr(self._bind_expr(expr, node.child))} {direction.upper()}"
                for expr, direction in node.keys
            )
            return (
                f"SELECT * FROM ({child_sql}) AS {_quote_ident(alias)} ORDER BY {keys}"
            )

        if isinstance(node, ra.GroupBy):
            child_sql = self._compile(node.child)
            alias = self._next_alias()
            group_cols = [
                _sql_expr(self._bind_expr(c, node.child)) for c in node.group_cols
            ]
            select_parts = list(group_cols)
            for fn, arg, agg_alias in node.aggregates:
                rendered = f"{fn.upper()}({_sql_expr(self._bind_expr(arg, node.child))})"
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
            left_s, right_s = self._schema(node.left), self._schema(node.right)
            if left_s and right_s:
                select_list = _join_on_select_list(left_s, right_s, la, ra_alias)
                return (
                    f"SELECT {select_list} FROM ({left}) AS {_quote_ident(la)} "
                    f"CROSS JOIN ({right}) AS {_quote_ident(ra_alias)}"
                )
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
                left_schema=self._schema(node.left),
                right_schema=self._schema(node.right),
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
                left_schema=self._schema(node.left),
                right_schema=self._schema(node.right),
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
                left_schema=self._schema(node.left),
                right_schema=self._schema(node.right),
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
                left_schema=self._schema(node.left),
                right_schema=self._schema(node.right),
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


def compile_relalg(
    node: ra.RANode,
    relation_columns: dict[str, list[str]] | None = None,
) -> str:
    return SqlCompiler(relation_columns).compile(node)
