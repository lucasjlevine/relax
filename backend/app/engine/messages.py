"""Turn engine/parser/DuckDB/sqlglot errors into RelAlg/SQL-facing messages."""

from __future__ import annotations

import re

# Lark / grammar terminal names → student-facing phrases
_TOKEN_WORDS: dict[str, str] = {
    "NAME": "a name (relation, attribute, or function)",
    "NUMBER": "a number",
    "STRING": "a string literal",
    "NULL": "null",
    "AGG_FN": "an aggregate (count, sum, avg, min, max)",
    "LPAR": "'('",
    "RPAR": "')'",
    "COMMA": "','",
    "STAR": "'*'",
    "SUB_OPEN": "a subscript _{…} or […]",
    "SUB_CLOSE": "'}' or ']'",
    "COMPARE_OP": "a comparison (=, <, >, …)",
    "ARROW": "→ or ->",
    "AND_OP": "AND",
    "OR_OP": "OR",
    "XOR_OP": "XOR",
    "NOT_OP": "NOT",
    "LIKE_OP": "LIKE or ILIKE",
    "ADD_OP": "'+'",
    "SUB_OP": "'-'",
    "MUL_OP": "'*'",
    "DIV_ARITH": "'/'",
    "MOD_OP": "'%'",
    "PROJ_OP": "π / pi",
    "SEL_OP": "σ / sigma",
    "RENAME_OP": "ρ / rho",
    "ORDER_OP": "τ / order by",
    "GROUP_OP": "γ / group by",
    "DIST_OP": "δ / distinct",
    "UNION_OP": "∪ / union",
    "INTERSECT_OP": "∩ / intersect",
    "EXCEPT_OP": "− / except",
    "CROSS_OP": "× / cross",
    "DIV_OP": "÷ / division",
    "JOIN_KIND": "a join",
    "JOIN_OP": "⋈ / join",
    "ON": "ON",
    "ORDER_DIR": "asc or desc",
    "WS": "whitespace",
    "COMMENT": "a comment",
    "ESCAPED": "an escaped character",
    "CASE": "CASE",
    "WHEN": "WHEN",
    "THEN": "THEN",
    "ELSE": "ELSE",
    "END": "END",
}


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _friendly_token(name: str) -> str:
    key = name.strip().upper()
    return _TOKEN_WORDS.get(key, name.lower().replace("_", " "))


def _extract_expected(text: str) -> list[str]:
    """Pull expected token names from a Lark error dump."""
    found: list[str] = []
    for m in re.finditer(r"\*\s*([A-Za-z_][A-Za-z0-9_]*)", text):
        tok = m.group(1)
        if tok.upper() in ("EXPECTED", "ONE", "OF", "UNEXPECTED"):
            continue
        found.append(tok)
    m = re.search(r"Expected[^:]*:\s*(.+)$", text, re.IGNORECASE | re.DOTALL)
    if m and not found:
        chunk = m.group(1)
        for part in re.split(r"[,/\s]+", chunk):
            part = part.strip(" *")
            if part and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", part):
                found.append(part)
    seen: set[str] = set()
    out: list[str] = []
    for t in found:
        u = t.upper()
        if u not in seen:
            seen.add(u)
            out.append(t)
    return out[:8]


def _format_expected(tokens: list[str]) -> str:
    if not tokens:
        return ""
    words = [_friendly_token(t) for t in tokens]
    if len(words) == 1:
        return f"Expected {words[0]}."
    if len(words) == 2:
        return f"Expected {words[0]} or {words[1]}."
    return "Expected one of: " + ", ".join(words[:-1]) + f", or {words[-1]}."


def _line_col_hint(text: str) -> str:
    m = re.search(r"[Ll]ine\s+(\d+)\s*,?\s*[Cc]ol(?:umn)?\s*(\d+)", text)
    if m:
        return f" (around line {m.group(1)}, column {m.group(2)})"
    return ""


def _sqlglot_node_name(text: str) -> str | None:
    m = re.search(
        r"<class 'sqlglot\.expressions\.[^']*\.(\w+)'>|sqlglot\.expressions[\w.]*\.(\w+)",
        text,
    )
    if not m:
        return None
    return m.group(1) or m.group(2)


def humanize_sql_syntax_error(raw: str) -> str:
    """Map sqlglot / SQL parser noise to short student-facing guidance."""
    original = _strip_ansi(str(raw).strip())
    text = " ".join(original.split())
    loc = _line_col_hint(text)
    node = _sqlglot_node_name(text)
    lower = text.lower()

    # Already humanized by validator
    if text.startswith("SQL syntax error:") or text.startswith("SQL mode only"):
        return text if text.startswith("SQL") else f"SQL syntax error: {text}"

    # Multiple WITH / CTE structure
    if "with" in lower and (
        "required keyword" in lower
        or "missing" in lower
        or "unexpected" in lower
        or "invalid" in lower
    ):
        if re.search(r"\bwith\b.+\bwith\b", lower) or "second with" in lower:
            return (
                "SQL syntax error: use one WITH with comma-separated CTEs, "
                "not multiple WITH blocks.\n"
                "Example:\n"
                "WITH Engineering AS (SELECT * FROM Employee WHERE dept = 'Engineering'),\n"
                "     Sales AS (SELECT * FROM Employee WHERE dept = 'Sales')\n"
                "SELECT * FROM Engineering\n"
                "UNION ALL\n"
                "SELECT * FROM Sales"
            )

    # UNION / INTERSECT / EXCEPT need SELECT expressions
    if node in ("Union", "Intersect", "Except") or re.search(
        r"\b(union|intersect|except)\b", lower
    ):
        if "expression" in lower and ("missing" in lower or "required" in lower):
            return (
                "SQL syntax error: each side of UNION / INTERSECT / EXCEPT must be a "
                "SELECT (not a bare relation name)."
                f"{loc}\n"
                "Write:\n"
                "  SELECT * FROM Engineering\n"
                "  UNION ALL\n"
                "  SELECT * FROM Sales\n"
                "instead of: Engineering UNION ALL Sales"
            )

    # Generic "Required keyword: 'X' missing for <class ...>"
    m = re.search(
        r"Required keyword:\s*'([^']+)'\s*missing for\s*(?:<class '[^']+'>)?",
        text,
        re.IGNORECASE,
    )
    if m:
        kw = m.group(1)
        what = node or "this clause"
        tip = {
            "expression": (
                f"SQL syntax error: a required expression is missing in {what}{loc}. "
                "For UNION, each side needs SELECT …; for WITH, add a final SELECT after the CTEs."
            ),
            "this": (
                f"SQL syntax error: a required part of {what} is missing{loc}. "
                "Check parentheses and keywords near that spot."
            ),
        }.get(
            kw.lower(),
            f"SQL syntax error: missing “{kw}” in {what}{loc}. "
            "Check the clause structure around that position.",
        )
        return tip

    # Unexpected token
    m = re.search(
        r"Unexpected token\s+(?:Token\()?['\"]?([^'\"\s,)\]]+)",
        text,
        re.IGNORECASE,
    )
    if m or "unexpected token" in lower or "invalid expression" in lower:
        got = m.group(1) if m else None
        head = (
            f"SQL syntax error near “{got}”{loc}."
            if got
            else f"SQL syntax error{loc}."
        )
        return (
            f"{head} Check for a missing comma between WITH CTEs, "
            "a missing SELECT after WITH, or a typo in keywords."
        )

    # Empty / incomplete
    if "empty" in lower or "no expression" in lower:
        return "SQL syntax error: the query is empty or incomplete."

    # Strip sqlglot class paths and ANSI leftovers for fallback
    cleaned = re.sub(r"<class '[^']+'>", "", text)
    cleaned = re.sub(r"sqlglot\.[\w.]+", "", cleaned)
    cleaned = re.sub(r"^SQL parse error:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split()).strip(" .")
    if len(cleaned) > 220:
        cleaned = cleaned[:217] + "…"
    return f"SQL syntax error{loc}: {cleaned}" if cleaned else f"SQL syntax error{loc}."


def humanize_query_error(raw: str, *, language: str = "relalg") -> str:
    original = _strip_ansi(str(raw).strip())
    text = " ".join(original.split())
    if not text:
        return "Something went wrong running this query."

    # DuckDB / binder
    m = re.search(
        r'Referenced column ["“]?([^"”]+)["”]? not found',
        text,
        re.IGNORECASE,
    )
    if m:
        return (
            f"Unknown attribute “{m.group(1)}”. "
            "Check spelling against the Schema panel, or qualify it as Relation.attribute."
        )

    m = re.search(
        r'Table with name ["“]?([^"”]+)["”]? does not exist',
        text,
        re.IGNORECASE,
    )
    if m:
        return (
            f"Unknown relation “{m.group(1)}”. "
            "Use a relation from the current dataset (see Schema), "
            "or a name you defined with WITH / RelAlg assignment."
        )

    m = re.search(
        r'Catalog Error:.*?["“]([^"”]+)["”]',
        text,
        re.IGNORECASE,
    )
    if m and "does not exist" in text.lower():
        return f"Unknown relation or attribute “{m.group(1)}”."

    if re.search(r"Binder Error", text, re.IGNORECASE):
        cleaned = re.sub(r"^.*?Binder Error:\s*", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*Candidate bindings:.*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*LINE \d+:.*$", "", cleaned, flags=re.IGNORECASE)
        return f"Query binding problem: {cleaned.strip()}"

    if re.search(r"Conversion Error|Type mismatch|Cannot compare", text, re.IGNORECASE):
        return (
            "Type mismatch in a comparison or function argument. "
            "Cast with date('YYYY-MM-DD'), or change the column type in Manage."
        )

    if "QUALIFY" in text.upper() and "WINDOW" in text.upper():
        return (
            "rownum() can only be used in projection lists or selection conditions "
            "(selections with rownum() are rewritten automatically)."
        )

    # SQL forbidden / mode
    if language == "sql" or "Statement type not allowed" in text:
        if "not allowed" in text.lower() and any(
            x in text.lower()
            for x in ("insert", "update", "delete", "drop", "create", "alter", "statement type")
        ):
            return (
                "SQL mode only allows SELECT "
                "(and UNION / INTERSECT / EXCEPT of SELECT statements)."
            )
        if "Only SELECT" in text:
            return (
                "SQL mode only allows SELECT "
                "(and UNION / INTERSECT / EXCEPT of SELECT statements)."
            )

    # Prefer dedicated SQL syntax humanizer for sqlglot-ish / parse messages
    sql_parse_markers = (
        "sqlglot",
        "Required keyword",
        "Unexpected token",
        "SQL parse error",
        "Invalid expression / Unexpected token",
        "Invalid expression",
        "Error tokenizing",
        "No expression",
    )
    if language == "sql" and (
        any(s.lower() in text.lower() for s in sql_parse_markers)
        or text.startswith("SQL syntax error")
        or text.startswith("Could not parse")
        or text.startswith("Only one SQL")
        or text.startswith("Query must not")
    ):
        if text.startswith(
            (
                "SQL syntax error",
                "SQL mode only",
                "Query must not",
                "Only one SQL",
                "Could not parse this SQL",
            )
        ):
            return original if "\n" in original and len(original) < 600 else text
        return humanize_sql_syntax_error(original)
    if language != "sql" and any(s in text for s in ("sqlglot", "SQL parse error")):
        return humanize_sql_syntax_error(original)

    # Lark / RelAlg parse — unexpected end of input
    if re.search(r"Unexpected end[- ]of[- ]input|EOF", text, re.IGNORECASE):
        expected = _format_expected(
            _extract_expected(original if "\n" in original else text)
        )
        base = (
            "RelAlg syntax error: the expression ends too early. "
            "Check for a missing relation name, closing parenthesis, "
            "or unfinished subscript _{…}."
        )
        return f"{base} {expected}".strip() if expected else base

    # Lark unexpected token / characters
    if (
        "Unexpected token" in text
        or "UnexpectedCharacters" in text
        or "Unexpected characters" in text
    ):
        m = re.search(
            r"Unexpected (?:token|characters)\s+[\"']?([^\"'\s,]+)[\"']?",
            text,
            re.IGNORECASE,
        )
        got = m.group(1) if m else None
        expected = _format_expected(
            _extract_expected(original if "\n" in original else text)
        )
        loc = _line_col_hint(text)
        if got and got.upper() not in ("TOKEN", "CHARACTERS"):
            head = f"RelAlg syntax error near “{got}”{loc}."
        else:
            head = f"RelAlg syntax error{loc}."
        tip = (
            "Check parentheses, subscripts _{…}, commas between list items, "
            "and that operators have the right arguments."
        )
        parts = [head]
        if expected:
            parts.append(expected)
        parts.append(tip)
        return " ".join(parts)

    if "Invalid RelAlg" in text:
        return (
            "That isn’t a complete RelAlg expression. "
            "Check operators, parentheses, and assignment lines (Name = expr)."
        )

    # Strip Python/DuckDB noise prefixes
    text = re.sub(r"^(Parser|Catalog|Binder|Invalid Input) Error:\s*", "", text)
    text = re.sub(r"\s*LINE \d+:.*$", "", text)
    if len(text) > 280:
        text = text[:277] + "…"
    return text


def humanize_parse_error(raw: str, *, language: str = "relalg") -> str:
    return humanize_query_error(raw, language=language)
