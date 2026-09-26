"""RelaX-compatible local_groups parsing and serialization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.datasets.loader import (
    ColumnDef,
    DatasetError,
    GroupDef,
    RelationDef,
    _parse_literal,
    _slugify,
    _split_csv_line,
)


@dataclass
class _PendingAssignment:
    name: str
    kind: str  # "inline" | "relalg"
    body: str


def _skip_ws_comments(text: str, i: int) -> int:
    n = len(text)
    while i < n:
        if text[i] in " \t\r\n":
            i += 1
            continue
        if text.startswith("--", i):
            # RelaX: -- comment needs space after -- (we accept both)
            nl = text.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        break
    return i


def _read_balanced_brace(text: str, open_idx: int) -> int:
    """open_idx at '{'; return index after matching '}'."""
    depth = 0
    i = open_idx
    n = len(text)
    in_single = in_double = False
    while i < n:
        ch = text[i]
        if in_single:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == "'":
                if i + 1 < n and text[i + 1] == "'":
                    i += 2
                    continue
                in_single = False
            i += 1
            continue
        if in_double:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            i += 1
            continue
        if ch == '"':
            in_double = True
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise DatasetError("Unclosed '{' in group definition")


def _read_multiline_brackets(text: str, open_idx: int) -> tuple[str, int]:
    """open_idx at first '[' of [[; return (body, index after ]])."""
    if not text.startswith("[[", open_idx):
        raise DatasetError("Expected [[")
    i = open_idx + 2
    n = len(text)
    buf: list[str] = []
    while i < n:
        if text.startswith("\\]]", i):
            buf.append("]]")
            i += 3
            continue
        if text.startswith("]]", i):
            return "".join(buf), i + 2
        buf.append(text[i])
        i += 1
    raise DatasetError("Unclosed [[ … ]] header")


def _parse_header_line(text: str, i: int) -> tuple[str, str, int] | None:
    """Parse group/description/category/example* headers. Returns (key, body, next_i) or None."""
    i = _skip_ws_comments(text, i)
    m = re.match(
        r"(group|description|category|exampleRelAlg|exampleSql)(?:@[a-z]+)?",
        text[i:],
        re.IGNORECASE,
    )
    if not m:
        return None
    key = m.group(1)
    # Normalize example key casing
    key_map = {
        "group": "group",
        "description": "description",
        "category": "category",
        "examplerelalg": "exampleRelAlg",
        "examplesql": "exampleSql",
    }
    key = key_map[key.lower()]
    i = i + m.end()
    i = _skip_ws_comments(text, i)
    if i < len(text) and text.startswith("[[", i):
        body, i = _read_multiline_brackets(text, i)
        return key, body.strip(), i
    if i < len(text) and text[i] == ":":
        i += 1
        # rest of line
        nl = text.find("\n", i)
        if nl < 0:
            body = text[i:]
            i = len(text)
        else:
            body = text[i:nl]
            i = nl + 1
        return key, body.strip(), i
    # RelaX exampleSql - { … } / exampleRelAlg - { … }
    if key in ("exampleRelAlg", "exampleSql"):
        i = _skip_ws_comments(text, i)
        if i < len(text) and text[i] == "-":
            i = _skip_ws_comments(text, i + 1)
            if i < len(text) and text[i] == "{":
                end = _read_balanced_brace(text, i)
                body = text[i + 1 : end - 1]
                return key, body.strip(), end
    return None


def _parse_assignment(text: str, i: int) -> tuple[_PendingAssignment, int] | None:
    i = _skip_ws_comments(text, i)
    m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*=", text[i:])
    if not m:
        return None
    name = m.group(1)
    i = i + m.end()
    i = _skip_ws_comments(text, i)
    if i < len(text) and text[i] == "{":
        end = _read_balanced_brace(text, i)
        body = text[i + 1 : end - 1]
        return _PendingAssignment(name=name, kind="inline", body=body), end
    # RelAlg expression until next header/assignment at line start or EOF
    start = i
    n = len(text)
    while i < n:
        # Look ahead for next top-level assignment or group header at bol
        if text[i] == "\n":
            j = _skip_ws_comments(text, i + 1)
            if j >= n:
                i = n
                break
            rest = text[j:]
            if re.match(
                r"(group|description|category|exampleRelAlg|exampleSql)(?:@[a-z]+)?\s*(:|\[\[|-)",
                rest,
                re.IGNORECASE,
            ):
                break
            if re.match(r"[A-Za-z_][A-Za-z0-9_]*\s*=", rest):
                break
        i += 1
    body = text[start:i].strip()
    if not body:
        raise DatasetError(f"Empty assignment for {name}")
    return _PendingAssignment(name=name, kind="relalg", body=body), i


def _parse_relation_body(body: str) -> tuple[list[ColumnDef], list[list[Any]]]:
    # Strip line comments
    cleaned_lines: list[str] = []
    for ln in body.splitlines():
        stripped = ln.strip()
        if not stripped or stripped.startswith("--"):
            continue
        cleaned_lines.append(stripped)
    if not cleaned_lines:
        raise DatasetError("Empty relation body (need a header row inside { … })")
    if cleaned_lines == ["()"]:
        raise DatasetError("Dee () is not supported; define columns explicitly")

    header = cleaned_lines[0]
    # Allow ; as delimiter in header by normalizing
    header_norm = header.replace(";", ",")
    cols: list[ColumnDef] = []
    for part in _split_csv_line(header_norm):
        part = part.strip()
        if not part:
            continue
        # Optional Qualifier.col
        if "." in part.split(":")[0]:
            part = part.split(".", 1)[1]
        if ":" in part:
            name, typ = part.split(":", 1)
            cols.append(ColumnDef(name=name.strip(), type_name=typ.strip().lower()))
        else:
            cols.append(ColumnDef(name=part, type_name="string"))

    rows: list[list[Any]] = []
    for line in cleaned_lines[1:]:
        line_norm = line.replace(";", ",")
        cells = _split_csv_line(line_norm)
        if len(cells) != len(cols):
            raise DatasetError(
                f"Row has {len(cells)} values but header has {len(cols)} columns: {line}"
            )
        # Infer types from first data row if still default string and looks numeric
        row = [
            _parse_literal(cell, cols[i].type_name) for i, cell in enumerate(cells)
        ]
        rows.append(row)

    # Infer types when all string and values look like numbers/dates/bools
    if rows and all(c.type_name == "string" for c in cols):
        for ci, col in enumerate(cols):
            vals = [r[ci] for r in rows if r[ci] is not None]
            if not vals:
                continue
            if all(isinstance(v, bool) or str(v).lower() in ("true", "false") for v in vals):
                col.type_name = "boolean"
            elif all(isinstance(v, (int, float)) for v in vals):
                col.type_name = "number"
            elif all(isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in vals):
                col.type_name = "date"

    return cols, rows


def _parse_group_chunk(chunk: str) -> GroupDef:
    name = ""
    description = ""
    category = ""
    example_relalg: str | None = None
    example_sql: str | None = None
    pending: list[_PendingAssignment] = []

    i = 0
    n = len(chunk)
    while i < n:
        i = _skip_ws_comments(chunk, i)
        if i >= n:
            break
        header = _parse_header_line(chunk, i)
        if header:
            key, body, i = header
            if key == "group":
                name = body
            elif key == "description":
                description = body
            elif key == "category":
                category = body
            elif key == "exampleRelAlg":
                example_relalg = body
            elif key == "exampleSql":
                example_sql = body
            continue
        assign = _parse_assignment(chunk, i)
        if assign:
            pending.append(assign[0])
            i = assign[1]
            continue
        # Skip unknown line
        nl = chunk.find("\n", i)
        if nl < 0:
            break
        i = nl + 1

    if not name:
        raise DatasetError("Group missing name (need `group: …`)")

    relations: dict[str, RelationDef] = {}
    derived: list[tuple[str, str]] = []
    for p in pending:
        if p.kind == "inline":
            columns, rows = _parse_relation_body(p.body)
            if not columns:
                raise DatasetError(f"Relation '{p.name}' has no columns")
            relations[p.name] = RelationDef(name=p.name, columns=columns, rows=rows)
        else:
            derived.append((p.name, p.body))

    if not relations and not derived:
        raise DatasetError(f"Group '{name}' has no relations")

    group = GroupDef(
        id=_slugify(name),
        name=name,
        description=description,
        relations=relations,
        example_relalg=example_relalg,
        example_sql=example_sql,
    )
    # stash category / derived for materialization
    setattr(group, "_category", category)
    setattr(group, "_derived", derived)
    return group


def parse_local_groups(text: str, *, materialize: bool = True) -> list[GroupDef]:
    """Parse RelaX-compatible local_groups text into GroupDef objects."""
    text = text.replace("\r\n", "\n")
    group_starts = [
        m.start()
        for m in re.finditer(
            r"(?m)^group(?:@[a-z]+)?\s*(:|\[\[)",
            text,
        )
    ]
    if not group_starts:
        raise DatasetError("No groups found (need a line starting with `group:`)")

    groups: list[GroupDef] = []
    for i, start in enumerate(group_starts):
        end = group_starts[i + 1] if i + 1 < len(group_starts) else len(text)
        chunk = text[start:end].strip()
        groups.append(_parse_group_chunk(chunk))

    if materialize:
        for g in groups:
            _materialize_derived(g)
            if not g.relations:
                raise DatasetError(f"Group '{g.name}' has no relations")

    # unique ids within one file
    seen: dict[str, int] = {}
    for g in groups:
        base = g.id
        count = seen.get(base, 0)
        seen[base] = count + 1
        if count:
            g.id = f"{base}-{count}"
    return groups


def _materialize_derived(group: GroupDef) -> None:
    derived: list[tuple[str, str]] = getattr(group, "_derived", []) or []
    if not derived:
        return
    from app.engine.executor import execute_relalg

    if not group.relations:
        raise DatasetError(
            f"Cannot derive relations in '{group.name}' with no base tables"
        )

    for name, expr in derived:
        try:
            result = execute_relalg(group, expr, limit=50_000, offset=0)
        except Exception as exc:  # noqa: BLE001
            raise DatasetError(
                f"Failed to materialize derived relation '{name}': {exc}"
            ) from exc
        columns = [
            ColumnDef(name=c.name, type_name=_normalize_col_type(c.type))
            for c in result.columns
        ]
        group.relations[name] = RelationDef(
            name=name, columns=columns, rows=list(result.rows)
        )
    setattr(group, "_derived", [])


def _normalize_col_type(type_name: str) -> str:
    t = (type_name or "string").lower()
    if t in ("number", "int", "integer", "double", "float", "decimal", "bigint"):
        return "number"
    if t in ("boolean", "bool") or "bool" in t:
        return "boolean"
    if t == "date" or "date" in t or "time" in t:
        return "date"
    if t in ("string", "str", "varchar", "text", "char"):
        return "string"
    return "string"


def format_group_text(group: GroupDef) -> str:
    """Serialize a GroupDef to RelaX-compatible local_groups text."""
    lines: list[str] = [f"group:{group.name}"]
    if group.description:
        if "\n" in group.description:
            lines.append(f"description[[{group.description}]]")
        else:
            lines.append(f"description:{group.description}")
    cat = getattr(group, "_category", "") or ""
    if cat:
        lines.append(f"category:{cat}")
    lines.append("")
    if group.example_relalg:
        lines.append("exampleRelAlg - {")
        lines.append(group.example_relalg.strip())
        lines.append("}")
        lines.append("")
    if group.example_sql:
        lines.append("exampleSql - {")
        lines.append(group.example_sql.strip())
        lines.append("}")
        lines.append("")
    for rel in group.relations.values():
        header = ", ".join(f"{c.name}:{c.type_name}" for c in rel.columns)
        lines.append(f"{rel.name} = {{")
        lines.append(header)
        for row in rel.rows:
            cells: list[str] = []
            for v in row:
                if v is None:
                    cells.append("null")
                elif isinstance(v, bool):
                    cells.append("true" if v else "false")
                elif isinstance(v, str):
                    if re.fullmatch(r"[0-9A-Za-z\-_.]+", v):
                        cells.append(v)
                    else:
                        cells.append("'" + v.replace("'", "''") + "'")
                else:
                    cells.append(str(v))
            lines.append(", ".join(cells))
        lines.append("}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_and_preview(text: str) -> list[GroupDef]:
    return parse_local_groups(text, materialize=True)
