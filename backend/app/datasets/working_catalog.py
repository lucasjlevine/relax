from __future__ import annotations

import copy
import re
from threading import Lock
from typing import Any

from app.datasets.loader import (
    ColumnDef,
    DatasetCatalog,
    DatasetError,
    GroupDef,
    RelationDef,
    TYPE_MAP,
)
from app.datasets.user_store import SAFE_NAME, UserDatasetStore


class WorkingCatalog:
    """Mutable catalog over deep-copied built-in groups plus user uploads."""

    def __init__(self, static: DatasetCatalog, users: UserDatasetStore) -> None:
        self.static = static
        self.users = users
        self._lock = Lock()
        self._groups: dict[str, GroupDef] = {}
        self.reload_static()

    def reload_static(self) -> None:
        with self._lock:
            self._groups = {
                g.id: copy.deepcopy(g) for g in self.static.list_groups()
            }

    def list_groups(self) -> list[GroupDef]:
        with self._lock:
            built_in = list(self._groups.values())
        return built_in + self.users.list_groups()

    def get(self, group_id: str) -> GroupDef:
        with self._lock:
            if group_id in self._groups:
                return self._groups[group_id]
        return self.users.get(group_id)

    def _is_user(self, group_id: str) -> bool:
        try:
            self.users.get(group_id)
            return True
        except DatasetError:
            return False

    def _mutate(self, group_id: str) -> GroupDef:
        """Return a mutable GroupDef; user groups stay in UserDatasetStore."""
        if self._is_user(group_id):
            return self.users.get(group_id)
        with self._lock:
            if group_id not in self._groups:
                raise DatasetError(f"Unknown dataset: {group_id}")
            return self._groups[group_id]

    def delete_group(self, group_id: str) -> None:
        with self._lock:
            if group_id in self._groups:
                del self._groups[group_id]
                return
        if self._is_user(group_id):
            with self.users._lock:
                if group_id in self.users._groups:
                    del self.users._groups[group_id]
                    return
        raise DatasetError(f"Unknown dataset: {group_id}")

    def rename_group(self, group_id: str, name: str) -> GroupDef:
        name = name.strip()
        if not name:
            raise DatasetError("Dataset name cannot be empty")
        group = self._mutate(group_id)
        group.name = name
        return group

    def add_relation(
        self,
        group_id: str,
        *,
        relation_name: str,
        columns: list[dict[str, str]],
        rows: list[list[Any]] | None = None,
    ) -> GroupDef:
        if not SAFE_NAME.match(relation_name):
            raise DatasetError(f"Invalid relation name: {relation_name}")
        group = self._mutate(group_id)
        if relation_name in group.relations:
            raise DatasetError(f"Relation already exists: {relation_name}")
        col_defs = _column_defs(columns)
        row_data = rows or []
        coerced_rows: list[list[Any]] = []
        for values in row_data:
            if len(values) != len(col_defs):
                raise DatasetError(
                    f"Expected {len(col_defs)} values, got {len(values)}"
                )
            coerced_rows.append(
                [
                    _coerce_value(values[i], col_defs[i].type_name)
                    for i in range(len(col_defs))
                ]
            )
        group.relations[relation_name] = RelationDef(
            name=relation_name, columns=col_defs, rows=coerced_rows
        )
        return group

    def attach_relation(self, group_id: str, relation: RelationDef) -> GroupDef:
        group = self._mutate(group_id)
        if relation.name in group.relations:
            raise DatasetError(f"Relation already exists: {relation.name}")
        group.relations[relation.name] = relation
        return group

    def rename_relation(
        self, group_id: str, relation_name: str, new_name: str
    ) -> GroupDef:
        if not SAFE_NAME.match(new_name):
            raise DatasetError(f"Invalid relation name: {new_name}")
        group = self._mutate(group_id)
        if relation_name not in group.relations:
            raise DatasetError(f"Unknown relation: {relation_name}")
        if new_name in group.relations and new_name != relation_name:
            raise DatasetError(f"Relation already exists: {new_name}")
        rel = group.relations.pop(relation_name)
        rel.name = new_name
        group.relations[new_name] = rel
        return group

    def delete_relation(self, group_id: str, relation_name: str) -> GroupDef:
        group = self._mutate(group_id)
        if relation_name not in group.relations:
            raise DatasetError(f"Unknown relation: {relation_name}")
        if len(group.relations) <= 1:
            raise DatasetError("Cannot delete the last relation in a dataset")
        del group.relations[relation_name]
        return group

    def rename_column(
        self,
        group_id: str,
        relation_name: str,
        column_name: str,
        new_name: str,
    ) -> GroupDef:
        if not SAFE_NAME.match(new_name):
            raise DatasetError(f"Invalid column name: {new_name}")
        group = self._mutate(group_id)
        if relation_name not in group.relations:
            raise DatasetError(f"Unknown relation: {relation_name}")
        rel = group.relations[relation_name]
        names = [c.name for c in rel.columns]
        if column_name not in names:
            raise DatasetError(f"Unknown column: {column_name}")
        if new_name in names and new_name != column_name:
            raise DatasetError(f"Column already exists: {new_name}")
        for col in rel.columns:
            if col.name == column_name:
                col.name = new_name
                break
        return group

    def change_column_type(
        self,
        group_id: str,
        relation_name: str,
        column_name: str,
        new_type: str,
    ) -> GroupDef:
        new_type = _normalize_type(new_type)
        group = self._mutate(group_id)
        if relation_name not in group.relations:
            raise DatasetError(f"Unknown relation: {relation_name}")
        rel = group.relations[relation_name]
        names = [c.name for c in rel.columns]
        if column_name not in names:
            raise DatasetError(f"Unknown column: {column_name}")
        idx = names.index(column_name)
        if rel.columns[idx].type_name == new_type:
            return group
        # Best-effort: strip currency/noise; unparseable cells become null.
        coerced_rows: list[list[Any]] = []
        for row in rel.rows:
            new_row = list(row)
            new_row[idx] = _coerce_value(row[idx], new_type, strict=False)
            coerced_rows.append(new_row)
        rel.columns[idx].type_name = new_type
        rel.rows = coerced_rows
        return group

    def add_column(
        self,
        group_id: str,
        relation_name: str,
        *,
        name: str,
        type_name: str = "string",
        default: Any = None,
    ) -> GroupDef:
        if not SAFE_NAME.match(name):
            raise DatasetError(f"Invalid column name: {name}")
        type_name = _normalize_type(type_name)
        group = self._mutate(group_id)
        if relation_name not in group.relations:
            raise DatasetError(f"Unknown relation: {relation_name}")
        rel = group.relations[relation_name]
        if any(c.name == name for c in rel.columns):
            raise DatasetError(f"Column already exists: {name}")
        fill = _coerce_value(default, type_name, strict=False)
        rel.columns.append(ColumnDef(name=name, type_name=type_name))
        rel.rows = [list(row) + [fill] for row in rel.rows]
        return group

    def delete_column(
        self, group_id: str, relation_name: str, column_name: str
    ) -> GroupDef:
        group = self._mutate(group_id)
        if relation_name not in group.relations:
            raise DatasetError(f"Unknown relation: {relation_name}")
        rel = group.relations[relation_name]
        names = [c.name for c in rel.columns]
        if column_name not in names:
            raise DatasetError(f"Unknown column: {column_name}")
        if len(rel.columns) <= 1:
            raise DatasetError("Cannot delete the last column in a relation")
        idx = names.index(column_name)
        rel.columns = [c for i, c in enumerate(rel.columns) if i != idx]
        rel.rows = [
            [cell for i, cell in enumerate(row) if i != idx] for row in rel.rows
        ]
        return group

    def add_row(
        self, group_id: str, relation_name: str, values: list[Any]
    ) -> GroupDef:
        group = self._mutate(group_id)
        if relation_name not in group.relations:
            raise DatasetError(f"Unknown relation: {relation_name}")
        rel = group.relations[relation_name]
        if len(values) != len(rel.columns):
            raise DatasetError(
                f"Expected {len(rel.columns)} values, got {len(values)}"
            )
        coerced = [
            _coerce_value(values[i], rel.columns[i].type_name)
            for i in range(len(rel.columns))
        ]
        rel.rows.append(coerced)
        return group

    def update_row(
        self,
        group_id: str,
        relation_name: str,
        row_index: int,
        values: list[Any],
    ) -> GroupDef:
        group = self._mutate(group_id)
        if relation_name not in group.relations:
            raise DatasetError(f"Unknown relation: {relation_name}")
        rel = group.relations[relation_name]
        if row_index < 0 or row_index >= len(rel.rows):
            raise DatasetError(f"Row index out of range: {row_index}")
        if len(values) != len(rel.columns):
            raise DatasetError(
                f"Expected {len(rel.columns)} values, got {len(values)}"
            )
        coerced = [
            _coerce_value(values[i], rel.columns[i].type_name)
            for i in range(len(rel.columns))
        ]
        rel.rows[row_index] = coerced
        return group

    def delete_row(
        self, group_id: str, relation_name: str, row_index: int
    ) -> GroupDef:
        group = self._mutate(group_id)
        if relation_name not in group.relations:
            raise DatasetError(f"Unknown relation: {relation_name}")
        rel = group.relations[relation_name]
        if row_index < 0 or row_index >= len(rel.rows):
            raise DatasetError(f"Row index out of range: {row_index}")
        del rel.rows[row_index]
        return group

    def set_rows(
        self, group_id: str, relation_name: str, rows: list[list[Any]]
    ) -> GroupDef:
        group = self._mutate(group_id)
        if relation_name not in group.relations:
            raise DatasetError(f"Unknown relation: {relation_name}")
        rel = group.relations[relation_name]
        coerced_rows: list[list[Any]] = []
        for values in rows:
            if len(values) != len(rel.columns):
                raise DatasetError(
                    f"Expected {len(rel.columns)} values, got {len(values)}"
                )
            coerced_rows.append(
                [
                    _coerce_value(values[i], rel.columns[i].type_name)
                    for i in range(len(rel.columns))
                ]
            )
        rel.rows = coerced_rows
        return group


def _column_defs(columns: list[dict[str, str]]) -> list[ColumnDef]:
    if not columns:
        raise DatasetError("Relation needs at least one column")
    col_defs: list[ColumnDef] = []
    seen: set[str] = set()
    for c in columns:
        cname = (c.get("name") or "").strip()
        ctype = _normalize_type(c.get("type") or "string")
        if not SAFE_NAME.match(cname):
            raise DatasetError(f"Invalid column name: {cname}")
        if cname in seen:
            raise DatasetError(f"Duplicate column name: {cname}")
        seen.add(cname)
        col_defs.append(ColumnDef(name=cname, type_name=ctype))
    return col_defs


def _normalize_type(type_name: str) -> str:
    ctype = type_name.strip().lower()
    aliases = {
        "int": "number",
        "integer": "number",
        "float": "number",
        "double": "number",
        "bool": "boolean",
        "str": "string",
        "text": "string",
        "varchar": "string",
    }
    ctype = aliases.get(ctype, ctype)
    if ctype not in TYPE_MAP and ctype not in (
        "number",
        "string",
        "boolean",
        "date",
    ):
        raise DatasetError(f"Invalid column type: {type_name}")
    return ctype


_CURRENCY_PREFIX = re.compile(
    r"^(?:A\$|C\$|US\$|AUD|USD|CAD|EUR|GBP|NZD)\s*",
    re.IGNORECASE,
)
_CURRENCY_SYMBOLS = re.compile(r"[$€£¥₹₩]")


def _parse_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if not text or text.lower() in ("null", "none", "nan", "-", "n/a", "na"):
        return None
    text = _CURRENCY_PREFIX.sub("", text)
    text = _CURRENCY_SYMBOLS.sub("", text)
    text = text.replace(",", "")
    text = text.replace(" ", "")
    if text.endswith("%"):
        text = text[:-1]
    text = text.strip()
    if not text or text in (".", "+", "-"):
        raise ValueError(f"Not a number: {value!r}")
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d*\.\d+", text) or re.fullmatch(r"-?\d+\.\d*", text):
        return float(text)
    if re.fullmatch(r"-?\d+(\.\d+)?[eE][+-]?\d+", text):
        return float(text)
    raise ValueError(f"Not a number: {value!r}")


def _coerce_value(value: Any, type_name: str, *, strict: bool = True) -> Any:
    if value is None or value == "":
        return None
    try:
        if type_name in ("boolean", "bool"):
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            text = str(value).strip().lower()
            if text in ("true", "1", "t", "yes", "y"):
                return True
            if text in ("false", "0", "f", "no", "n"):
                return False
            if strict:
                raise ValueError(f"Not a boolean: {value!r}")
            return None
        if type_name in ("number", "int", "integer"):
            return _parse_number(value)
        if type_name == "date":
            return str(value).strip()
        return str(value)
    except (TypeError, ValueError):
        if strict:
            raise
        return None
