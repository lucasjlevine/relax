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


def _sql_expr(node: object) -> str:
    if isinstance(node, ra.ColumnRef):
        if node.relation:
            return f"{_quote_ident(node.relation)}.{_quote_ident(node.name)}"
        return _quote_ident(node.name)
    if isinstance(node, ra.Literal):
        return _sql_literal(node.value)
    if isinstance(node, ra.BinaryExpr):
        op = node.op
        if op == "<>":
            op = "!="
        if op in ("and", "or"):
            return f"({_sql_expr(node.left)} {op.upper()} {_sql_expr(node.right)})"
        return f"({_sql_expr(node.left)} {op} {_sql_expr(node.right)})"
    if isinstance(node, ra.UnaryExpr):
        if node.op == "not":
            return f"(NOT {_sql_expr(node.operand)})"
        raise CompileError(f"Unsupported unary op: {node.op}")
    raise CompileError(f"Unsupported expression: {node!r}")


class SqlCompiler:
    def __init__(self) -> None:
        self._alias = 0

    def _next_alias(self, prefix: str = "t") -> str:
        self._alias += 1
        return f"{prefix}{self._alias}"

    def compile(self, node: ra.RANode) -> str:
        sql = self._compile(node)
        return f"SELECT * FROM ({sql}) AS {_quote_ident(self._next_alias('root'))}"

    def _compile(self, node: ra.RANode) -> str:
        if isinstance(node, ra.Relation):
            return f"SELECT * FROM {_quote_ident(node.name)}"

        if isinstance(node, ra.Projection):
            child_sql = self._compile(node.child)
            alias = self._next_alias()
            parts: list[str] = []
            for expr, col_alias in node.items:
                rendered = _sql_expr(expr)
                if col_alias:
                    parts.append(f"{rendered} AS {_quote_ident(col_alias)}")
                elif isinstance(expr, ra.ColumnRef):
                    parts.append(rendered)
                else:
                    parts.append(rendered)
            select_list = ", ".join(parts) if parts else "*"
            return (
                f"SELECT DISTINCT {select_list} FROM ({child_sql}) AS {_quote_ident(alias)}"
            )

        if isinstance(node, ra.Selection):
            child_sql = self._compile(node.child)
            alias = self._next_alias()
            cond = _sql_expr(node.condition)
            return f"SELECT * FROM ({child_sql}) AS {_quote_ident(alias)} WHERE {cond}"

        if isinstance(node, ra.RenameRelation):
            # Relation rename is mostly for qualification; SQL uses subquery alias.
            child_sql = self._compile(node.child)
            return f"SELECT * FROM ({child_sql}) AS {_quote_ident(node.new_name)}"

        if isinstance(node, ra.RenameColumns):
            child_sql = self._compile(node.child)
            alias = self._next_alias()
            # SELECT * REPLACE is DuckDB-specific; use explicit renames via aliases.
            # We select all columns with renames applied for mapped names.
            mapping = {old: new for old, new in node.mapping}
            # Without schema introspection here, emit REPLACE-style using aliases:
            # SELECT col AS new ... requires knowing columns. Use DuckDB COLUMNS(*) workaround:
            # Fall back to selecting mapped columns with aliases and * EXCLUDE.
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
            left = self._compile(node.left)
            right = self._compile(node.right)
            la, ra_alias = self._next_alias("l"), self._next_alias("r")
            return (
                f"SELECT * FROM ({left}) AS {_quote_ident(la)} "
                f"NATURAL JOIN ({right}) AS {_quote_ident(ra_alias)}"
            )

        if isinstance(node, ra.ThetaJoin):
            left = self._compile(node.left)
            right = self._compile(node.right)
            la, ra_alias = self._next_alias("l"), self._next_alias("r")
            cond = _sql_expr(node.condition)
            return (
                f"SELECT * FROM ({left}) AS {_quote_ident(la)} "
                f"INNER JOIN ({right}) AS {_quote_ident(ra_alias)} ON {cond}"
            )

        raise CompileError(f"Unsupported RelAlg node: {type(node).__name__}")


def compile_relalg(node: ra.RANode) -> str:
    return SqlCompiler().compile(node)
