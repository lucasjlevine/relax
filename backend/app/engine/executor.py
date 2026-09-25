from __future__ import annotations

import time
from typing import Any

import duckdb

from app.datasets.loader import TYPE_MAP, GroupDef
from app.models.schemas import ColumnInfo, OperatorTreeNode, QueryResponse
from app.parsers.relalg import ast as ra
from app.parsers.relalg.parser import RelAlgParseError, parse_relalg
from app.parsers.sql.validator import SqlValidationError, validate_sql
from app.engine.compiler import CompileError, SqlCompiler, _quote_ident
from app.engine.tree import build_operator_tree


class QueryError(Exception):
    def __init__(self, message: str, code: str = "query_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _duck_type(logical: str) -> str:
    return TYPE_MAP.get(logical.lower(), "VARCHAR")


def register_group(conn: duckdb.DuckDBPyConnection, group: GroupDef) -> None:
    for rel in group.relations.values():
        cols_sql = ", ".join(
            f'"{col.name}" {_duck_type(col.type_name)}' for col in rel.columns
        )
        conn.execute(f'CREATE TABLE "{rel.name}" ({cols_sql})')
        if not rel.rows:
            continue
        placeholders = ", ".join(["?"] * len(rel.columns))
        conn.executemany(
            f'INSERT INTO "{rel.name}" VALUES ({placeholders})',
            rel.rows,
        )


def _map_duck_type(type_str: str) -> str:
    t = type_str.upper()
    if any(x in t for x in ("INT", "DOUBLE", "FLOAT", "DECIMAL", "HUGEINT", "NUMERIC")):
        return "number"
    if "BOOL" in t:
        return "boolean"
    if "DATE" in t or "TIME" in t:
        return "date"
    return "string"


def _serialize_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class SchemaAwareCompiler(SqlCompiler):
    """Compiler that introspects temporary results for division."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        super().__init__()
        self.conn = conn

    def _columns_of(self, sql: str) -> list[str]:
        rows = self.conn.execute(f"DESCRIBE SELECT * FROM ({sql}) AS _d").fetchall()
        return [r[0] for r in rows]

    def _compile(self, node: ra.RANode) -> str:
        if not isinstance(node, ra.Division):
            return SqlCompiler._compile(self, node)

        left = self._compile(node.left)
        right = self._compile(node.right)
        lcols = self._columns_of(left)
        rcols = self._columns_of(right)
        if not set(rcols).issubset(set(lcols)):
            raise CompileError(
                f"Division requires right columns ⊆ left columns; got {rcols} vs {lcols}"
            )
        quotient_cols = [c for c in lcols if c not in rcols]
        if not quotient_cols:
            raise CompileError("Division result would have no columns")
        qlist = ", ".join(_quote_ident(c) for c in quotient_cols)
        rlist = ", ".join(_quote_ident(c) for c in rcols)
        return f"""
            SELECT DISTINCT {qlist} FROM ({left}) AS _r
            EXCEPT
            SELECT {qlist} FROM (
              SELECT {qlist}, {rlist} FROM (
                SELECT DISTINCT {qlist} FROM ({left}) AS _q
              ) AS _qq CROSS JOIN ({right}) AS _s
              EXCEPT
              SELECT {qlist}, {rlist} FROM ({left}) AS _rr
            ) AS _incomplete
            """


def execute_sql(
    group: GroupDef,
    sql: str,
    *,
    limit: int,
    offset: int,
    tree: OperatorTreeNode | None = None,
    warnings: list[str] | None = None,
) -> QueryResponse:
    conn = duckdb.connect(database=":memory:")
    try:
        conn.execute("SET enable_external_access=false")
        register_group(conn, group)

        count_sql = f"SELECT COUNT(*) FROM ({sql}) AS _count_sub"
        start = time.perf_counter()
        try:
            total = int(conn.execute(count_sql).fetchone()[0])
            limited = (
                f"SELECT * FROM ({sql}) AS _page "
                f"LIMIT {int(limit)} OFFSET {int(offset)}"
            )
            relation = conn.execute(limited)
        except duckdb.Error as exc:
            raise QueryError(str(exc), code="execution_error") from exc
        elapsed_ms = (time.perf_counter() - start) * 1000

        description = relation.description or []
        columns = [
            ColumnInfo(name=col[0], type=_map_duck_type(str(col[1])))
            for col in description
        ]
        rows = [[_serialize_cell(v) for v in row] for row in relation.fetchall()]
        return QueryResponse(
            columns=columns,
            rows=rows,
            rowCount=total,
            executionMs=round(elapsed_ms, 3),
            tree=tree,
            warnings=warnings or [],
        )
    finally:
        conn.close()


def execute_relalg(
    group: GroupDef,
    query: str,
    *,
    limit: int,
    offset: int,
) -> QueryResponse:
    try:
        ast = parse_relalg(query)
        tree = build_operator_tree(ast)
    except RelAlgParseError as exc:
        raise QueryError(exc.message, code="parse_error") from exc

    conn = duckdb.connect(database=":memory:")
    try:
        conn.execute("SET enable_external_access=false")
        register_group(conn, group)
        try:
            sql = SchemaAwareCompiler(conn).compile(ast)
        except CompileError as exc:
            raise QueryError(exc.message, code="compile_error") from exc

        count_sql = f"SELECT COUNT(*) FROM ({sql}) AS _count_sub"
        start = time.perf_counter()
        try:
            total = int(conn.execute(count_sql).fetchone()[0])
            limited = (
                f"SELECT * FROM ({sql}) AS _page "
                f"LIMIT {int(limit)} OFFSET {int(offset)}"
            )
            relation = conn.execute(limited)
        except duckdb.Error as exc:
            raise QueryError(str(exc), code="execution_error") from exc
        elapsed_ms = (time.perf_counter() - start) * 1000
        description = relation.description or []
        columns = [
            ColumnInfo(name=col[0], type=_map_duck_type(str(col[1])))
            for col in description
        ]
        rows = [[_serialize_cell(v) for v in row] for row in relation.fetchall()]
        return QueryResponse(
            columns=columns,
            rows=rows,
            rowCount=total,
            executionMs=round(elapsed_ms, 3),
            tree=tree,
            warnings=[],
        )
    finally:
        conn.close()


def execute_sql_query(
    group: GroupDef,
    query: str,
    *,
    limit: int,
    offset: int,
) -> QueryResponse:
    try:
        sql = validate_sql(query)
    except SqlValidationError as exc:
        raise QueryError(exc.message, code="parse_error") from exc

    tree = OperatorTreeNode(
        id="1",
        label="SQL",
        operator="sql",
        children=[
            OperatorTreeNode(id="2", label="SELECT", operator="select", children=[])
        ],
    )
    return execute_sql(group, sql, limit=limit, offset=offset, tree=tree)
