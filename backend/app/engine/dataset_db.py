"""Fingerprint-keyed DuckDB file cache + bulk table registration.

Cold path materializes a temp DuckDB file once per dataset fingerprint.
Queries ATTACH it READ_ONLY into a fresh :memory: connection so concurrent
Executes do not share mutable connection state, then disable external access.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from app.config import get_settings
from app.datasets.loader import TYPE_MAP, GroupDef

_MAX_CACHED = 4
_lock = threading.Lock()
_cache: OrderedDict[str, "CacheEntry"] = OrderedDict()
_cache_root = Path(tempfile.gettempdir()) / "relax-duckdb-cache"
_cache_root.mkdir(parents=True, exist_ok=True)

_BATCH_INSERT = 500


@dataclass
class CacheEntry:
    group_id: str
    fingerprint: str
    path: Path


def _duck_type(logical: str) -> str:
    return TYPE_MAP.get(logical.lower(), "VARCHAR")


def configure_conn(conn: duckdb.DuckDBPyConnection) -> None:
    settings = get_settings()
    conn.execute("SET enable_external_access=false")
    mem = (settings.duckdb_memory_limit or "256MB").strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?\s*(?:B|KB|MB|GB|TB)", mem, re.I):
        mem = "256MB"
    conn.execute("SET memory_limit=?", [mem])
    threads = max(1, min(8, int(settings.duckdb_threads)))
    conn.execute(f"SET threads={threads}")


def _csv_cell(value: Any) -> str:
    if value is None:
        return r"\N"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _insert_rows_csv(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    columns: list[str],
    rows: list[list[Any]],
) -> None:
    """Bulk-load rows via a temp CSV (far faster than executemany)."""
    fd, path = tempfile.mkstemp(prefix="relax-rel-", suffix=".csv")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(
                fh,
                lineterminator="\n",
                quoting=csv.QUOTE_MINIMAL,
                escapechar="\\",
            )
            for row in rows:
                writer.writerow([_csv_cell(v) for v in row])
        path_sql = path.replace("'", "''")
        safe = table.replace('"', '""')
        conn.execute(
            f"""
            COPY "{safe}" FROM '{path_sql}' (
                HEADER false,
                DELIMITER ',',
                QUOTE '"',
                ESCAPE '\\',
                NULL '\\N',
                FORMAT CSV
            )
            """
        )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _insert_rows_batched(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    n_cols: int,
    rows: list[list[Any]],
) -> None:
    placeholders = "(" + ", ".join(["?"] * n_cols) + ")"
    safe = table.replace('"', '""')
    for i in range(0, len(rows), _BATCH_INSERT):
        chunk = rows[i : i + _BATCH_INSERT]
        values_sql = ", ".join([placeholders] * len(chunk))
        flat = [v for row in chunk for v in row]
        conn.execute(f'INSERT INTO "{safe}" VALUES {values_sql}', flat)


def register_group(conn: duckdb.DuckDBPyConnection, group: GroupDef) -> None:
    """Create tables for ``group`` and bulk-load rows."""
    for rel in group.relations.values():
        cols_sql = ", ".join(
            f'"{col.name}" {_duck_type(col.type_name)}' for col in rel.columns
        )
        conn.execute(f'CREATE TABLE "{rel.name}" ({cols_sql})')
        if not rel.rows:
            continue
        try:
            _insert_rows_csv(
                conn,
                rel.name,
                [c.name for c in rel.columns],
                rel.rows,
            )
        except duckdb.Error:
            # Fall back if CSV typing/escaping disagrees with column types.
            _insert_rows_batched(conn, rel.name, len(rel.columns), rel.rows)


def group_fingerprint(group: GroupDef) -> str:
    """Stable content fingerprint (schema + row counts + updated_at)."""
    parts: list[str] = [
        group.id,
        group.updated_at or "",
        "1" if group.owner_id else "0",
    ]
    for name in sorted(group.relations):
        rel = group.relations[name]
        col_sig = ",".join(f"{c.name}:{c.type_name}" for c in rel.columns)
        parts.append(f"{name}|{col_sig}|{len(rel.rows)}")
    raw = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def invalidate(group_id: str) -> None:
    """Drop cached DuckDB file for a dataset (best-effort)."""
    with _lock:
        entry = _cache.pop(group_id, None)
    if entry is not None:
        _unlink_quiet(entry.path)


def clear_all() -> None:
    """Test helper: empty the entire cache."""
    with _lock:
        entries = list(_cache.values())
        _cache.clear()
    for entry in entries:
        _unlink_quiet(entry.path)


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _evict_unlocked() -> None:
    while len(_cache) > _MAX_CACHED:
        _gid, entry = _cache.popitem(last=False)
        _unlink_quiet(entry.path)


def _ensure_cached(group: GroupDef) -> CacheEntry:
    fp = group_fingerprint(group)
    with _lock:
        entry = _cache.get(group.id)
        if entry is not None and entry.fingerprint == fp and entry.path.is_file():
            _cache.move_to_end(group.id)
            return entry
        stale_path = entry.path if entry is not None else None
        if entry is not None:
            _cache.pop(group.id, None)

    if stale_path is not None:
        _unlink_quiet(stale_path)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f"relax-{group.id}-",
        suffix=".duckdb",
        dir=_cache_root,
    )
    os.close(fd)
    path = Path(tmp_name)
    try:
        path.unlink(missing_ok=True)
        build = duckdb.connect(str(path))
        try:
            register_group(build, group)
            build.execute("CHECKPOINT")
        finally:
            build.close()
    except Exception:
        _unlink_quiet(path)
        raise

    entry = CacheEntry(group_id=group.id, fingerprint=fp, path=path)
    with _lock:
        old = _cache.pop(group.id, None)
        if old is not None and old.path != path:
            _unlink_quiet(old.path)
        _cache[group.id] = entry
        _cache.move_to_end(group.id)
        _evict_unlocked()
        return entry


def open_query_connection(group: GroupDef) -> duckdb.DuckDBPyConnection:
    """
    Open a sandboxed :memory: connection with ``group`` tables available.

    Tables are views over a READ_ONLY ATTACH of the cached DuckDB file.
    """
    entry = _ensure_cached(group)
    conn = duckdb.connect(database=":memory:")
    try:
        path_sql = str(entry.path).replace("'", "''")
        conn.execute(f"ATTACH '{path_sql}' AS _relax_ds (READ_ONLY)")
        for rel_name in group.relations:
            safe = rel_name.replace('"', '""')
            conn.execute(
                f'CREATE VIEW "{safe}" AS SELECT * FROM _relax_ds."{safe}"'
            )
        configure_conn(conn)
        return conn
    except Exception:
        conn.close()
        raise
