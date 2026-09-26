from __future__ import annotations

import time
from typing import Any

import duckdb

from app.datasets.loader import TYPE_MAP, GroupDef
from app.models.schemas import (
    ColumnInfo,
    OperatorTreeNode,
    QueryResponse,
    QueryResultBlock,
)
from app.parsers.relalg import ast as ra
from app.parsers.relalg.parser import RelAlgParseError, parse_relalg
from app.parsers.relalg.statements import split_relalg_statements
from app.parsers.sql.validator import SqlValidationError, validate_sql
from app.engine.compiler import CompileError, SqlCompiler, _quote_ident
from app.engine.tree import build_operator_tree


from app.engine.messages import humanize_parse_error, humanize_query_error


class QueryError(Exception):
    def __init__(self, message: str, code: str = "query_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _raise_exec(exc: Exception, *, language: str) -> None:
    raise QueryError(
        humanize_query_error(str(exc), language=language),
        code="execution_error",
    ) from exc


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
            _raise_exec(exc, language="sql")
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
    extra_warnings: list[str] | None = None,
) -> QueryResponse:
    statements = split_relalg_statements(query)
    if not statements:
        raise QueryError("Query must not be empty", code="validation_error")

    parsed: list[tuple[ra.RANode, str | None]] = []
    for body, label in statements:
        try:
            ast = parse_relalg(body)
        except RelAlgParseError as exc:
            prefix = f"{label}: " if label else ""
            raise QueryError(
                prefix + humanize_parse_error(exc.message), code="parse_error"
            ) from exc
        parsed.append((ast, label))

    blocks: list[QueryResultBlock] = []
    total_ms = 0.0
    all_warnings: list[str] = list(extra_warnings or [])

    conn = duckdb.connect(database=":memory:")
    try:
        conn.execute("SET enable_external_access=false")
        register_group(conn, group)
        compiler = SchemaAwareCompiler(conn)

        for idx, (ast, label) in enumerate(parsed):
            try:
                tree = build_operator_tree(ast)
                sql = compiler.compile(ast)
            except CompileError as exc:
                prefix = f"{label}: " if label else ""
                raise QueryError(
                    prefix + humanize_query_error(exc.message, language="relalg"),
                    code="compile_error",
                ) from exc

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
                prefix = f"{label}: " if label else ""
                raise QueryError(
                    prefix + humanize_query_error(str(exc), language="relalg"),
                    code="execution_error",
                ) from exc
            elapsed_ms = (time.perf_counter() - start) * 1000
            total_ms += elapsed_ms
            description = relation.description or []
            columns = [
                ColumnInfo(name=col[0], type=_map_duck_type(str(col[1])))
                for col in description
            ]
            rows = [
                [_serialize_cell(v) for v in row] for row in relation.fetchall()
            ]
            blocks.append(
                QueryResultBlock(
                    index=idx,
                    label=label or (f"Statement {idx + 1}" if len(parsed) > 1 else None),
                    columns=columns,
                    rows=rows,
                    rowCount=total,
                    executionMs=round(elapsed_ms, 3),
                    tree=tree,
                    warnings=[],
                )
            )
    finally:
        conn.close()

    primary = blocks[-1]
    return QueryResponse(
        columns=primary.columns,
        rows=primary.rows,
        rowCount=primary.rowCount,
        executionMs=round(total_ms, 3),
        tree=primary.tree,
        warnings=all_warnings,
        results=blocks,
    )


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
        raise QueryError(
            humanize_query_error(exc.message, language="sql"),
            code="parse_error",
        ) from exc

    tree = OperatorTreeNode(
        id="1",
        label="SQL",
        operator="sql",
        children=[
            OperatorTreeNode(id="2", label="SELECT", operator="select", children=[])
        ],
    )
    single = execute_sql(group, sql, limit=limit, offset=offset, tree=tree)
    single.results = [
        QueryResultBlock(
            index=0,
            label=None,
            columns=single.columns,
            rows=single.rows,
            rowCount=single.rowCount,
            executionMs=single.executionMs,
            tree=single.tree,
            warnings=list(single.warnings),
        )
    ]
    return single
