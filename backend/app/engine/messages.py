"""Turn engine/parser/DuckDB errors into RelAlg/SQL-facing messages."""

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
}


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
    # Also match "Expected one of: A, B, C" style
    m = re.search(r"Expected[^:]*:\s*(.+)$", text, re.IGNORECASE | re.DOTALL)
    if m and not found:
        chunk = m.group(1)
        for part in re.split(r"[,/\s]+", chunk):
            part = part.strip(" *")
            if part and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", part):
                found.append(part)
    # Dedupe while preserving order
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


def humanize_query_error(raw: str, *, language: str = "relalg") -> str:
    # Preserve newlines briefly for expected-token extraction, then normalize.
    original = str(raw).strip()
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
            "Use a relation from the current dataset (see Schema)."
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

    # SQL forbidden statements
    if language == "sql" or "Statement type not allowed" in text:
        m = re.search(r"Statement type not allowed:\s*(\w+)", text, re.IGNORECASE)
        if m or "not allowed" in text.lower() and any(
            x in text.lower() for x in ("insert", "update", "delete", "drop", "create", "alter")
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

    # Lark / RelAlg parse — unexpected end of input
    if re.search(r"Unexpected end[- ]of[- ]input|EOF", text, re.IGNORECASE):
        expected = _format_expected(_extract_expected(original if "\n" in original else text))
        lang = "RelAlg" if language == "relalg" else "SQL"
        base = (
            f"{lang} syntax error: the expression ends too early. "
            "Check for a missing relation name, closing parenthesis, or unfinished subscript _{…}."
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
        expected = _format_expected(_extract_expected(original if "\n" in original else text))
        lang = "RelAlg" if language == "relalg" else "SQL"
        if got and got.upper() not in ("TOKEN", "CHARACTERS"):
            head = f"{lang} syntax error near “{got}”."
        else:
            head = f"{lang} syntax error."
        tip = "Check parentheses, subscripts _{…}, and operator placement."
        parts = [head]
        if expected:
            parts.append(expected)
        parts.append(tip)
        return " ".join(parts)

    if "Invalid RelAlg" in text:
        return "That isn’t a complete RelAlg expression. Check operators and parentheses."

    # SQL validation leftovers
    if language == "sql":
        cleaned = re.sub(r"^SQL parse error:\s*", "", text, flags=re.IGNORECASE)
        return f"SQL syntax error. {cleaned}"

    # Strip Python/DuckDB noise prefixes
    text = re.sub(r"^(Parser|Catalog|Binder|Invalid Input) Error:\s*", "", text)
    text = re.sub(r"\s*LINE \d+:.*$", "", text)
    if len(text) > 280:
        text = text[:277] + "…"
    return text


def humanize_parse_error(raw: str, *, language: str = "relalg") -> str:
    return humanize_query_error(raw, language=language)
