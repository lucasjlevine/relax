"""SQL validation and light teaching-friendly normalization."""

from __future__ import annotations

import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError as SqlglotParseError


class SqlValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


_FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.TruncateTable,
)

_SET_OP = re.compile(
    r"\b(UNION(?:\s+ALL|\s+DISTINCT)?|INTERSECT(?:\s+ALL|\s+DISTINCT)?|"
    r"EXCEPT(?:\s+ALL|\s+DISTINCT)?)\b",
    re.IGNORECASE,
)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_WITH = re.compile(r"\bWITH\b", re.IGNORECASE)
_AS = re.compile(r"\bAS\b", re.IGNORECASE)


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _skip_ws_and_comments(text: str, i: int) -> int:
    n = len(text)
    while i < n:
        if text[i] in " \t\r\n":
            i += 1
            continue
        if text.startswith("--", i):
            nl = text.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        break
    return i


def _match_kw(text: str, i: int, pattern: re.Pattern[str]) -> re.Match[str] | None:
    i = _skip_ws_and_comments(text, i)
    m = pattern.match(text, i)
    return m


def _read_balanced_parens(text: str, open_idx: int) -> int:
    """open_idx points at '('; return index after matching ')'."""
    depth = 0
    i = open_idx
    n = len(text)
    in_single = False
    in_double = False
    while i < n:
        ch = text[i]
        if in_single:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == "'":
                # SQL '' escape
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
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise SqlValidationError(
        "SQL syntax error: missing closing ')' in a WITH … AS ( … ) definition."
    )


def _parse_cte_list(text: str, i: int) -> tuple[list[str], int]:
    """Parse one or more `name AS (…)` CTEs starting after WITH. Returns CTE sql fragments."""
    ctes: list[str] = []
    while True:
        i = _skip_ws_and_comments(text, i)
        m = _IDENT.match(text, i)
        if not m:
            raise SqlValidationError(
                "SQL syntax error in WITH: expected a CTE name after WITH "
                "(example: WITH Eng AS (SELECT …) SELECT …)."
            )
        name = m.group(0)
        i = m.end()
        as_m = _match_kw(text, i, _AS)
        if not as_m:
            raise SqlValidationError(
                f"SQL syntax error in WITH: expected AS after CTE name “{name}”."
            )
        i = _skip_ws_and_comments(text, as_m.end())
        if i >= len(text) or text[i] != "(":
            raise SqlValidationError(
                f"SQL syntax error in WITH: expected '(' after “{name} AS”."
            )
        end = _read_balanced_parens(text, i)
        body = text[i:end]  # includes parens
        ctes.append(f"{name} AS {body}")
        i = _skip_ws_and_comments(text, end)
        if i < len(text) and text[i] == ",":
            i += 1
            continue
        # Another WITH starts a new list of CTEs to merge
        with_m = _match_kw(text, i, _WITH)
        if with_m:
            i = with_m.end()
            continue
        break
    return ctes, i


def _rewrite_bare_set_ops(final: str) -> str:
    """
    Rewrite `A UNION ALL B` / `A INTERSECT B` (bare names) into
    `SELECT * FROM A UNION ALL SELECT * FROM B`.
    Leave alone if either side already looks like a SELECT/subquery.
    """
    text = final.strip()
    if not text:
        return text

    # Already has SELECT somewhere — don't rewrite whole thing blindly
    # unless the pattern is strictly Ident SETOP Ident (optional more setops).
    parts: list[str] = []
    ops: list[str] = []
    pos = 0
    while True:
        pos = _skip_ws_and_comments(text, pos)
        if pos >= len(text):
            return final
        # parenthesized subquery or SELECT → no bare rewrite
        if text[pos] == "(" or text[pos : pos + 6].upper() == "SELECT":
            return final
        m = _IDENT.match(text, pos)
        if not m:
            return final
        parts.append(m.group(0))
        pos = _skip_ws_and_comments(text, m.end())
        if pos >= len(text):
            break
        op_m = _SET_OP.match(text, pos)
        if not op_m:
            return final
        ops.append(op_m.group(0))
        pos = op_m.end()

    if len(parts) < 2 or len(ops) != len(parts) - 1:
        return final

    chunks = [f"SELECT * FROM {parts[0]}"]
    for op, name in zip(ops, parts[1:], strict=True):
        chunks.append(f"{op} SELECT * FROM {name}")
    return " ".join(chunks)


def normalize_teaching_sql(query: str) -> str:
    """
    Accept common teaching forms and rewrite to standard SQL:
    - Multiple consecutive WITH blocks → one WITH with comma-separated CTEs
    - Bare `A UNION ALL B` after CTEs → SELECT * FROM A UNION ALL SELECT * FROM B
    """
    text = query.strip().rstrip(";").strip()
    if not text:
        return text

    i = _skip_ws_and_comments(text, 0)
    with_m = _match_kw(text, i, _WITH)
    if not with_m:
        # Still allow bare set-op rewrite for simple cases
        return _rewrite_bare_set_ops(text)

    ctes, after = _parse_cte_list(text, with_m.end())
    final = text[after:].strip()
    if not final:
        raise SqlValidationError(
            "SQL syntax error: a WITH clause needs a final SELECT "
            "(or UNION of SELECTs). Example:\n"
            "WITH Eng AS (SELECT * FROM Employee WHERE dept = 'Engineering')\n"
            "SELECT * FROM Eng"
        )

    final = _rewrite_bare_set_ops(final)
    return "WITH " + ",\n".join(ctes) + "\n" + final


def validate_sql(query: str) -> str:
    """Parse and validate a read-only SQL SELECT (DuckDB dialect). Returns normalized SQL."""
    text = query.strip().rstrip(";")
    if not text:
        raise SqlValidationError("Query must not be empty")

    try:
        normalized = normalize_teaching_sql(text)
    except SqlValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 — fall through to raw parse with better errors
        normalized = text
        _ = exc

    try:
        statements = sqlglot.parse(normalized, read="duckdb")
    except SqlglotParseError as exc:
        # Retry original if normalize somehow broke a valid query
        if normalized != text:
            try:
                statements = sqlglot.parse(text, read="duckdb")
                normalized = text
            except SqlglotParseError:
                raise SqlValidationError(_strip_ansi(str(exc))) from exc
        else:
            raise SqlValidationError(_strip_ansi(str(exc))) from exc

    if not statements or statements[0] is None:
        raise SqlValidationError(
            "Could not parse this SQL. Check for a missing SELECT, "
            "unfinished WITH, or a typo near the end of the query."
        )
    if len(statements) > 1:
        raise SqlValidationError(
            "Only one SQL statement is allowed. "
            "Combine steps with a single WITH (comma-separated CTEs), "
            "not multiple statements separated by semicolons."
        )

    statement = statements[0]
    for node in statement.walk():
        if isinstance(node, _FORBIDDEN):
            raise SqlValidationError(
                "SQL mode only allows SELECT "
                "(and UNION / INTERSECT / EXCEPT of SELECT statements)."
            )

    if not isinstance(statement, (exp.Select, exp.Union, exp.Except, exp.Intersect)):
        if not any(isinstance(n, exp.Select) for n in statement.walk()):
            raise SqlValidationError(
                "SQL mode only allows SELECT "
                "(and UNION / INTERSECT / EXCEPT of SELECT statements)."
            )

    return statement.sql(dialect="duckdb")
