from __future__ import annotations

import csv
import io
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import duckdb

from app.datasets.loader import ColumnDef, DatasetError, GroupDef, RelationDef, TYPE_MAP


SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "upload"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_dataset_id() -> str:
    return f"ds_{uuid.uuid4().hex}"


def _new_share_token() -> str:
    return f"shr_{uuid.uuid4().hex}"


def _new_owner_id() -> str:
    return f"own_{uuid.uuid4().hex}"


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


def group_to_dict(group: GroupDef) -> dict[str, Any]:
    return {
        "id": group.id,
        "ownerId": group.owner_id,
        "shareToken": group.share_token,
        "name": group.name,
        "description": group.description,
        "exampleRelAlg": group.example_relalg,
        "exampleSql": group.example_sql,
        "forkedFrom": group.forked_from,
        "updatedAt": group.updated_at,
        "relations": {
            name: {
                "columns": [
                    {"name": c.name, "type": c.type_name} for c in rel.columns
                ],
                "rows": rel.rows,
            }
            for name, rel in group.relations.items()
        },
    }


def group_from_dict(data: dict[str, Any]) -> GroupDef:
    relations: dict[str, RelationDef] = {}
    for name, rel in (data.get("relations") or {}).items():
        columns = [
            ColumnDef(name=c["name"], type_name=c.get("type", "string"))
            for c in rel.get("columns") or []
        ]
        relations[name] = RelationDef(
            name=name,
            columns=columns,
            rows=list(rel.get("rows") or []),
        )
    return GroupDef(
        id=data["id"],
        name=data.get("name") or data["id"],
        description=data.get("description") or "",
        relations=relations,
        example_relalg=data.get("exampleRelAlg"),
        example_sql=data.get("exampleSql"),
        owner_id=data.get("ownerId"),
        share_token=data.get("shareToken"),
        forked_from=data.get("forkedFrom"),
        updated_at=data.get("updatedAt"),
    )


class UserDatasetStore:
    """Disk-backed catalog for uploaded / built / forked user datasets."""

    def __init__(
        self,
        upload_dir: Path,
        store_dir: Path,
        max_upload_bytes: int,
    ) -> None:
        self.upload_dir = upload_dir
        self.store_dir = store_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.max_upload_bytes = max_upload_bytes
        self._groups: dict[str, GroupDef] = {}
        self._by_share: dict[str, str] = {}
        self._lock = Lock()
        self._load_all()

    def _path_for(self, group_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_\-]", "_", group_id)
        return self.store_dir / f"{safe}.json"

    def _load_all(self) -> None:
        for path in sorted(self.store_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                group = group_from_dict(data)
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                continue
            self._groups[group.id] = group
            if group.share_token:
                self._by_share[group.share_token] = group.id

    def _flush(self, group: GroupDef) -> None:
        group.updated_at = _now_iso()
        path = self._path_for(group.id)
        payload = json.dumps(group_to_dict(group), indent=2, ensure_ascii=False)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{group.id}.",
            suffix=".tmp",
            dir=self.store_dir,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def list_groups(self) -> list[GroupDef]:
        with self._lock:
            return list(self._groups.values())

    def list_for_owner(self, owner_id: str) -> list[GroupDef]:
        with self._lock:
            return [g for g in self._groups.values() if g.owner_id == owner_id]

    def get(self, group_id: str) -> GroupDef:
        with self._lock:
            if group_id not in self._groups:
                raise DatasetError(f"Unknown dataset: {group_id}")
            return self._groups[group_id]

    def get_by_share_token(self, token: str) -> GroupDef:
        with self._lock:
            group_id = self._by_share.get(token)
            if not group_id or group_id not in self._groups:
                raise DatasetError("Unknown share link")
            return self._groups[group_id]

    def add_group(self, group: GroupDef) -> GroupDef:
        with self._lock:
            if not group.id:
                group.id = _new_dataset_id()
            if not group.share_token:
                group.share_token = _new_share_token()
            if not group.updated_at:
                group.updated_at = _now_iso()
            self._groups[group.id] = group
            if group.share_token:
                self._by_share[group.share_token] = group.id
            self._flush(group)
            return group

    def save_group(self, group: GroupDef) -> GroupDef:
        """Persist mutations to an existing user group."""
        with self._lock:
            if group.id not in self._groups:
                raise DatasetError(f"Unknown dataset: {group.id}")
            self._groups[group.id] = group
            if group.share_token:
                self._by_share[group.share_token] = group.id
            self._flush(group)
            return group

    def delete_group(self, group_id: str) -> None:
        with self._lock:
            group = self._groups.pop(group_id, None)
            if group is None:
                raise DatasetError(f"Unknown dataset: {group_id}")
            if group.share_token:
                self._by_share.pop(group.share_token, None)
            path = self._path_for(group_id)
            path.unlink(missing_ok=True)

    def fork_from(
        self,
        source: GroupDef,
        *,
        owner_id: str,
        name: str | None = None,
    ) -> GroupDef:
        import copy

        forked = copy.deepcopy(source)
        forked.id = _new_dataset_id()
        forked.owner_id = owner_id
        forked.share_token = _new_share_token()
        forked.forked_from = source.forked_from or source.id
        forked.name = name or f"{source.name} (copy)"
        if not forked.description:
            forked.description = f"Personal copy of {source.name}"
        elif "Personal copy" not in forked.description:
            forked.description = f"Personal copy of {source.name}. {forked.description}"
        forked.updated_at = _now_iso()
        return self.add_group(forked)

    def copy_for_owner(self, source: GroupDef, *, owner_id: str) -> GroupDef:
        """Clone a shared dataset into the caller's library."""
        return self.fork_from(
            source,
            owner_id=owner_id,
            name=source.name,
        )

    def from_csv(
        self,
        *,
        filename: str,
        content: bytes,
        owner_id: str,
        relation_name: str | None = None,
        dataset_name: str | None = None,
        has_header: bool = True,
        skip_rows: int = 0,
        delimiter: str = ",",
    ) -> GroupDef:
        rel = self.parse_csv_relation(
            filename=filename,
            content=content,
            relation_name=relation_name,
            has_header=has_header,
            skip_rows=skip_rows,
            delimiter=delimiter,
        )
        group = GroupDef(
            id=_new_dataset_id(),
            name=dataset_name or f"CSV: {filename}",
            description=f"Uploaded CSV ({filename})",
            relations={rel.name: rel},
            owner_id=owner_id,
            share_token=_new_share_token(),
        )
        return self.add_group(group)

    def parse_csv_relation(
        self,
        *,
        filename: str,
        content: bytes,
        relation_name: str | None = None,
        has_header: bool = True,
        skip_rows: int = 0,
        delimiter: str = ",",
    ) -> RelationDef:
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
            base = name
            n = 2
            while name in normalized_headers:
                name = f"{base}_{n}"
                n += 1
            normalized_headers.append(name)
        headers = normalized_headers

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
        return RelationDef(name=rel_name, columns=columns, rows=rows)

    def from_sqlite(self, *, filename: str, content: bytes, owner_id: str) -> GroupDef:
        if len(content) > self.max_upload_bytes:
            raise DatasetError(
                f"File exceeds max size of {self.max_upload_bytes // (1024 * 1024)} MB"
            )
        uid = uuid.uuid4().hex[:8]
        path = self.upload_dir / f"{uid}.db"
        path.write_bytes(content)
        try:
            conn = duckdb.connect(database=":memory:")
            conn.execute(f"ATTACH '{path}' AS upload (TYPE SQLITE, READ_ONLY)")
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog = 'upload' AND table_type = 'BASE TABLE'"
            ).fetchall()
            if not tables:
                tables = conn.execute(
                    "SELECT name FROM upload.sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            relations: dict[str, RelationDef] = {}
            for (tname,) in tables:
                if not SAFE_NAME.match(str(tname)):
                    continue
                describe = conn.execute(
                    f'DESCRIBE SELECT * FROM upload."{tname}"'
                ).fetchall()
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
            id=_new_dataset_id(),
            name=f"DB: {filename}",
            description=f"Uploaded SQLite database ({filename})",
            relations=relations,
            owner_id=owner_id,
            share_token=_new_share_token(),
        )
        return self.add_group(group)

    def from_builder(
        self,
        *,
        name: str,
        relation_name: str,
        columns: list[dict],
        rows: list[list],
        owner_id: str,
    ) -> GroupDef:
        if not SAFE_NAME.match(relation_name):
            raise DatasetError("Invalid relation name")
        col_defs = []
        for c in columns:
            cname = c["name"]
            ctype = c.get("type", "string")
            if not SAFE_NAME.match(cname):
                raise DatasetError(f"Invalid column name: {cname}")
            if ctype not in TYPE_MAP and ctype not in (
                "number",
                "string",
                "boolean",
                "date",
            ):
                raise DatasetError(f"Invalid column type: {ctype}")
            col_defs.append(ColumnDef(name=cname, type_name=ctype))
        group = GroupDef(
            id=_new_dataset_id(),
            name=name or f"Custom: {relation_name}",
            description="Built in the calculator",
            relations={
                relation_name: RelationDef(
                    name=relation_name, columns=col_defs, rows=rows
                )
            },
            owner_id=owner_id,
            share_token=_new_share_token(),
        )
        return self.add_group(group)

    def from_group_text(self, text: str, *, owner_id: str) -> list[GroupDef]:
        """Parse RelaX local_groups text and install each group as a user dataset."""
        from app.datasets.group_format import parse_local_groups

        groups = parse_local_groups(text, materialize=True)
        installed: list[GroupDef] = []
        for g in groups:
            g.id = _new_dataset_id()
            g.owner_id = owner_id
            g.share_token = _new_share_token()
            if not g.description:
                g.description = "Installed from Group Editor"
            installed.append(self.add_group(g))
        return installed


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
