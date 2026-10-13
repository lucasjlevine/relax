from __future__ import annotations

import re
import threading
import time
from typing import Any

import duckdb

from app.config import get_settings
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
    if isinstance(exc, duckdb.InterruptException) or "Interrupted" in str(exc):
        settings = get_settings()
        raise QueryError(
            f"Query exceeded the time limit ({settings.query_timeout_ms} ms). "
            "Simplify the expression (fewer joins / smaller intermediate results).",
            code="timeout",
        ) from exc
    raise QueryError(
        humanize_query_error(str(exc), language=language),
        code="execution_error",
    ) from exc


def _configure_conn(conn: duckdb.DuckDBPyConnection) -> None:
    settings = get_settings()
    conn.execute("SET enable_external_access=false")
    # Bound resource use on shared hosts (Silk).
    mem = (settings.duckdb_memory_limit or "256MB").strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?\s*(?:B|KB|MB|GB|TB)", mem, re.I):
        mem = "256MB"
    conn.execute("SET memory_limit=?", [mem])
    threads = max(1, min(8, int(settings.duckdb_threads)))
    conn.execute(f"SET threads={threads}")


def _execute_timed(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    *,
    timeout_ms: int,
) -> tuple[Any, list[Any]]:
    """
    Run ``conn.execute(sql)`` and ``fetchall()`` with an interruptible timeout.

    DuckDB has no statement_timeout setting; we interrupt from a watchdog thread.
    """
    box: dict[str, Any] = {}

    def worker() -> None:
        try:
            relation = conn.execute(sql)
            box["description"] = relation.description
            box["rows"] = relation.fetchall()
        except Exception as exc:  # noqa: BLE001 — surfaced to caller
            box["exc"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(max(0.05, timeout_ms / 1000.0))
    if thread.is_alive():
        try:
            conn.interrupt()
        except Exception:  # noqa: BLE001
            pass
        thread.join(2.0)
        raise QueryError(
            f"Query exceeded the time limit ({timeout_ms} ms). "
            "Simplify the expression (fewer joins / smaller intermediate results).",
            code="timeout",
        )
    if "exc" in box:
        raise box["exc"]
    return box.get("description"), box.get("rows") or []


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
    """Compiler with dataset schemas (Relation.attr provenance) and division support."""

    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        relation_columns: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(relation_columns)
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
    settings = get_settings()
    timeout_ms = max(100, int(settings.query_timeout_ms))
    conn = duckdb.connect(database=":memory:")
    try:
        _configure_conn(conn)
        register_group(conn, group)

        count_sql = f"SELECT COUNT(*) FROM ({sql}) AS _count_sub"
        start = time.perf_counter()
        try:
            _desc, count_rows = _execute_timed(
                conn, count_sql, timeout_ms=timeout_ms
            )
            total = int(count_rows[0][0]) if count_rows else 0
            limited = (
                f"SELECT * FROM ({sql}) AS _page "
                f"LIMIT {int(limit)} OFFSET {int(offset)}"
            )
            description, raw_rows = _execute_timed(
                conn, limited, timeout_ms=timeout_ms
            )
        except QueryError:
            raise
        except duckdb.Error as exc:
            _raise_exec(exc, language="sql")
        except Exception as exc:  # noqa: BLE001
            _raise_exec(exc, language="sql")
        elapsed_ms = (time.perf_counter() - start) * 1000

        columns = [
            ColumnInfo(name=col[0], type=_map_duck_type(str(col[1])))
            for col in (description or [])
        ]
        rows = [[_serialize_cell(v) for v in row] for row in raw_rows]
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
    settings = get_settings()
    timeout_ms = max(100, int(settings.query_timeout_ms))
    max_stmts = max(1, int(settings.max_relalg_statements))

    statements = split_relalg_statements(query)
    if not statements:
        raise QueryError("Query must not be empty", code="validation_error")
    if len(statements) > max_stmts:
        raise QueryError(
            f"Too many statements (max {max_stmts}). Split the work across Executes.",
            code="validation_error",
        )

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
        _configure_conn(conn)
        register_group(conn, group)
        relation_columns = {
            rel.name: [c.name for c in rel.columns]
            for rel in group.relations.values()
        }
        compiler = SchemaAwareCompiler(conn, relation_columns)

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
                _desc, count_rows = _execute_timed(
                    conn, count_sql, timeout_ms=timeout_ms
                )
                total = int(count_rows[0][0]) if count_rows else 0
                limited = (
                    f"SELECT * FROM ({sql}) AS _page "
                    f"LIMIT {int(limit)} OFFSET {int(offset)}"
                )
                description, raw_rows = _execute_timed(
                    conn, limited, timeout_ms=timeout_ms
                )
            except QueryError as exc:
                prefix = f"{label}: " if label else ""
                if prefix and not exc.message.startswith(prefix):
                    raise QueryError(prefix + exc.message, code=exc.code) from exc
                raise
            except duckdb.Error as exc:
                prefix = f"{label}: " if label else ""
                try:
                    _raise_exec(exc, language="relalg")
                except QueryError as qe:
                    raise QueryError(prefix + qe.message, code=qe.code) from exc
            elapsed_ms = (time.perf_counter() - start) * 1000
            total_ms += elapsed_ms
            columns = [
                ColumnInfo(name=col[0], type=_map_duck_type(str(col[1])))
                for col in (description or [])
            ]
            rows = [[_serialize_cell(v) for v in row] for row in raw_rows]
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
