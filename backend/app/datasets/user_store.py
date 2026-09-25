from __future__ import annotations

import csv
import io
import re
import uuid
from pathlib import Path
from threading import Lock

import duckdb

from app.datasets.loader import ColumnDef, DatasetError, GroupDef, RelationDef, TYPE_MAP


SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "upload"


def _infer_type(values: list[str]) -> str:
    nonempty = [v for v in values if v != "" and v.lower() != "null"]
    if not nonempty:
        return "string"
    if all(re.fullmatch(r"-?\d+", v) for v in nonempty):
        return "number"
    if all(re.fullmatch(r"-?\d+\.\d+", v) for v in nonempty):
        return "number"
    return "string"


def _parse_cell(raw: str, type_name: str):
    value = raw.strip()
    if value == "" or value.lower() == "null":
        return None
    if type_name == "number":
        return float(value) if "." in value else int(value)
    return value


class UserDatasetStore:
    """In-memory catalog for uploaded / built user datasets."""

    def __init__(self, upload_dir: Path, max_upload_bytes: int) -> None:
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.max_upload_bytes = max_upload_bytes
        self._groups: dict[str, GroupDef] = {}
        self._lock = Lock()

    def list_groups(self) -> list[GroupDef]:
        with self._lock:
            return list(self._groups.values())

    def get(self, group_id: str) -> GroupDef:
        with self._lock:
            if group_id not in self._groups:
                raise DatasetError(f"Unknown dataset: {group_id}")
            return self._groups[group_id]

    def add_group(self, group: GroupDef) -> GroupDef:
        with self._lock:
            self._groups[group.id] = group
            return group

    def from_csv(
        self,
        *,
        filename: str,
        content: bytes,
        relation_name: str | None = None,
        dataset_name: str | None = None,
        has_header: bool = True,
        skip_rows: int = 0,
        delimiter: str = ",",
    ) -> GroupDef:
        if len(content) > self.max_upload_bytes:
            raise DatasetError(
                f"File exceeds max size of {self.max_upload_bytes // (1024 * 1024)} MB"
            )
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text), delimiter=delimiter or ",")
        rows_raw = list(reader)
        if skip_rows:
            rows_raw = rows_raw[skip_rows:]
        if not rows_raw:
            raise DatasetError("CSV is empty after skipping rows")

        if has_header:
            headers = [h.strip() or f"col{i+1}" for i, h in enumerate(rows_raw[0])]
            data_rows = rows_raw[1:]
        else:
            width = max(len(r) for r in rows_raw)
            headers = [f"col{i+1}" for i in range(width)]
            data_rows = rows_raw

        normalized_headers: list[str] = []
        for i, h in enumerate(headers):
            name = re.sub(r"[^A-Za-z0-9_]", "_", h.strip()) or f"col{i+1}"
            if name[0].isdigit():
                name = f"c_{name}"
            # ensure uniqueness
            base = name
            n = 2
            while name in normalized_headers:
                name = f"{base}_{n}"
                n += 1
            normalized_headers.append(name)
        headers = normalized_headers

        # Pad/truncate rows to header width
        fixed_rows: list[list[str]] = []
        for row in data_rows:
            cells = list(row) + [""] * max(0, len(headers) - len(row))
            fixed_rows.append(cells[: len(headers)])

        col_values = list(zip(*fixed_rows)) if fixed_rows else [[] for _ in headers]
        columns = [
            ColumnDef(
                name=headers[i],
                type_name=_infer_type(list(col_values[i]) if col_values else []),
            )
            for i in range(len(headers))
        ]
        rows = [
            [_parse_cell(cell, columns[i].type_name) for i, cell in enumerate(row)]
            for row in fixed_rows
        ]
        rel_name = relation_name or _safe_rel_name(Path(filename).stem)
        if not SAFE_NAME.match(rel_name):
            raise DatasetError(f"Invalid relation name: {rel_name}")
        uid = str(uuid.uuid4())[:8]
        group = GroupDef(
            id=f"upload-csv-{uid}",
            name=dataset_name or f"CSV: {filename}",
            description=f"Uploaded CSV ({filename})",
            relations={
                rel_name: RelationDef(name=rel_name, columns=columns, rows=rows)
            },
        )
        return self.add_group(group)

    def from_sqlite(self, *, filename: str, content: bytes) -> GroupDef:
        if len(content) > self.max_upload_bytes:
            raise DatasetError(
                f"File exceeds max size of {self.max_upload_bytes // (1024 * 1024)} MB"
            )
        uid = str(uuid.uuid4())[:8]
        path = self.upload_dir / f"{uid}.db"
        path.write_bytes(content)
        try:
            conn = duckdb.connect(database=":memory:")
            # DuckDB can attach sqlite
            conn.execute(f"ATTACH '{path}' AS upload (TYPE SQLITE, READ_ONLY)")
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog = 'upload' AND table_type = 'BASE TABLE'"
            ).fetchall()
            if not tables:
                # fallback: sqlite_master via duckdb sqlite scan
                tables = conn.execute(
                    "SELECT name FROM upload.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            relations: dict[str, RelationDef] = {}
            for (tname,) in tables:
                if not SAFE_NAME.match(str(tname)):
                    continue
                describe = conn.execute(f'DESCRIBE SELECT * FROM upload."{tname}"').fetchall()
                columns = [
                    ColumnDef(
                        name=row[0],
                        type_name=_logical_from_duck(str(row[1])),
                    )
                    for row in describe
                ]
                data = conn.execute(f'SELECT * FROM upload."{tname}"').fetchall()
                relations[str(tname)] = RelationDef(
                    name=str(tname),
                    columns=columns,
                    rows=[list(r) for r in data],
                )
            conn.close()
        finally:
            path.unlink(missing_ok=True)

        if not relations:
            raise DatasetError("No tables found in database file")

        group = GroupDef(
            id=f"upload-db-{uid}",
            name=f"DB: {filename}",
            description=f"Uploaded SQLite database ({filename})",
            relations=relations,
        )
        return self.add_group(group)

    def from_builder(
        self,
        *,
        name: str,
        relation_name: str,
        columns: list[dict],
        rows: list[list],
    ) -> GroupDef:
        if not SAFE_NAME.match(relation_name):
            raise DatasetError("Invalid relation name")
        col_defs = []
        for c in columns:
            cname = c["name"]
            ctype = c.get("type", "string")
            if not SAFE_NAME.match(cname):
                raise DatasetError(f"Invalid column name: {cname}")
            if ctype not in TYPE_MAP and ctype not in ("number", "string", "boolean", "date"):
                raise DatasetError(f"Invalid column type: {ctype}")
            col_defs.append(ColumnDef(name=cname, type_name=ctype))
        uid = str(uuid.uuid4())[:8]
        group = GroupDef(
            id=f"custom-{uid}",
            name=name or f"Custom: {relation_name}",
            description="Built in the calculator",
            relations={
                relation_name: RelationDef(
                    name=relation_name, columns=col_defs, rows=rows
                )
            },
        )
        return self.add_group(group)


def _safe_rel_name(stem: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", stem)
    if not cleaned or cleaned[0].isdigit():
        cleaned = "R_" + cleaned
    return cleaned[:40] or "R"


def _logical_from_duck(duck_type: str) -> str:
    t = duck_type.upper()
    if any(x in t for x in ("INT", "DOUBLE", "FLOAT", "DECIMAL", "NUMERIC")):
        return "number"
    if "BOOL" in t:
        return "boolean"
    if "DATE" in t or "TIME" in t:
        return "date"
    return "string"
