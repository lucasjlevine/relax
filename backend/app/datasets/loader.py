from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class DatasetError(Exception):
    """Raised when a dataset file cannot be parsed or a group is missing."""


TYPE_MAP = {
    "number": "DOUBLE",
    "int": "INTEGER",
    "integer": "INTEGER",
    "string": "VARCHAR",
    "str": "VARCHAR",
    "date": "DATE",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
}


@dataclass
class ColumnDef:
    name: str
    type_name: str  # logical: number|string|date|boolean


@dataclass
class RelationDef:
    name: str
    columns: list[ColumnDef]
    rows: list[list[Any]]


@dataclass
class GroupDef:
    id: str
    name: str
    description: str = ""
    relations: dict[str, RelationDef] = field(default_factory=dict)
    example_relalg: str | None = None
    example_sql: str | None = None


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "group"


def _parse_literal(raw: str, type_name: str | None = None) -> Any:
    value = raw.strip()
    if value.lower() == "null":
        return None
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]
    if type_name in ("string", "str"):
        return value
    if type_name in ("boolean", "bool"):
        return value.lower() in ("true", "1", "t", "yes")
    if type_name in ("number", "int", "integer"):
        if "." in value:
            return float(value)
        return int(value)
    # Infer
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _split_csv_line(line: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quote: str | None = None
    for ch in line:
        if in_quote:
            current.append(ch)
            if ch == in_quote:
                in_quote = None
            continue
        if ch in ("'", '"'):
            in_quote = ch
            current.append(ch)
            continue
        if ch == ",":
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    parts.append("".join(current).strip())
    return parts


def _parse_header(header_line: str) -> list[ColumnDef]:
    cols: list[ColumnDef] = []
    for part in _split_csv_line(header_line):
        if ":" in part:
            name, typ = part.split(":", 1)
            cols.append(ColumnDef(name=name.strip(), type_name=typ.strip().lower()))
        else:
            cols.append(ColumnDef(name=part.strip(), type_name="string"))
    return cols


def _parse_relation_body(body: str) -> tuple[list[ColumnDef], list[list[Any]]]:
    lines = [ln.strip() for ln in body.strip().splitlines() if ln.strip()]
    if not lines:
        raise DatasetError("Empty relation body")
    columns = _parse_header(lines[0])
    rows: list[list[Any]] = []
    for line in lines[1:]:
        cells = _split_csv_line(line)
        if len(cells) != len(columns):
            raise DatasetError(
                f"Row has {len(cells)} values but header has {len(columns)} columns: {line}"
            )
        row = [
            _parse_literal(cell, columns[i].type_name) for i, cell in enumerate(cells)
        ]
        rows.append(row)
    return columns, rows


_MULTILINE_HEADER = re.compile(
    r"^(?P<key>group|description|exampleRelAlg|exampleSql)(?:@[a-z]+)?\s*\[\[(?P<body>.*?)\]\]",
    re.DOTALL | re.MULTILINE,
)
_SINGLE_HEADER = re.compile(
    r"^(?P<key>group|description|exampleRelAlg|exampleSql)(?:@[a-z]+)?\s*:\s*(?P<body>.+)$",
    re.MULTILINE,
)
_RELATION = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{(?P<body>.*?)\}",
    re.DOTALL | re.MULTILINE,
)


def parse_local_groups(text: str) -> list[GroupDef]:
    """Parse RelaX-compatible local_groups text into GroupDef objects."""
    # Normalize windows newlines
    text = text.replace("\r\n", "\n")

    # Find group start positions via "group:" or "group[["
    group_starts = [
        m.start()
        for m in re.finditer(r"(?m)^group(?:@[a-z]+)?\s*(:|\[\[)", text)
    ]
    if not group_starts:
        raise DatasetError("No groups found in dataset file")

    groups: list[GroupDef] = []
    for i, start in enumerate(group_starts):
        end = group_starts[i + 1] if i + 1 < len(group_starts) else len(text)
        chunk = text[start:end].strip()
        groups.append(_parse_group_chunk(chunk))
    return groups


def _parse_group_chunk(chunk: str) -> GroupDef:
    name = ""
    description = ""
    example_relalg: str | None = None
    example_sql: str | None = None

    for match in _MULTILINE_HEADER.finditer(chunk):
        key = match.group("key")
        body = match.group("body").strip()
        if key == "group":
            name = body
        elif key == "description":
            description = body
        elif key == "exampleRelAlg":
            example_relalg = body
        elif key == "exampleSql":
            example_sql = body

    for match in _SINGLE_HEADER.finditer(chunk):
        key = match.group("key")
        body = match.group("body").strip()
        if key == "group" and not name:
            name = body
        elif key == "description" and not description:
            description = body
        elif key == "exampleRelAlg" and example_relalg is None:
            example_relalg = body
        elif key == "exampleSql" and example_sql is None:
            example_sql = body

    if not name:
        raise DatasetError("Group missing name")

    relations: dict[str, RelationDef] = {}
    for match in _RELATION.finditer(chunk):
        rel_name = match.group("name")
        columns, rows = _parse_relation_body(match.group("body"))
        relations[rel_name] = RelationDef(name=rel_name, columns=columns, rows=rows)

    if not relations:
        raise DatasetError(f"Group '{name}' has no relations")

    return GroupDef(
        id=_slugify(name),
        name=name,
        description=description,
        relations=relations,
        example_relalg=example_relalg,
        example_sql=example_sql,
    )


class DatasetCatalog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._groups: dict[str, GroupDef] = {}
        self.reload()

    def reload(self) -> None:
        if not self.path.exists():
            raise DatasetError(f"Datasets file not found: {self.path}")
        text = self.path.read_text(encoding="utf-8")
        groups = parse_local_groups(text)
        self._groups = {g.id: g for g in groups}
        # Ensure unique ids if collisions (append index)
        seen: dict[str, int] = {}
        fixed: dict[str, GroupDef] = {}
        for g in groups:
            base = g.id
            count = seen.get(base, 0)
            seen[base] = count + 1
            if count:
                g.id = f"{base}-{count}"
            fixed[g.id] = g
        self._groups = fixed

    def list_groups(self) -> list[GroupDef]:
        return list(self._groups.values())

    def get(self, group_id: str) -> GroupDef:
        if group_id not in self._groups:
            raise DatasetError(f"Unknown dataset: {group_id}")
        return self._groups[group_id]
