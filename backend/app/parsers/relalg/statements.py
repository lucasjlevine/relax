"""Split RelAlg source into semicolon-terminated statements."""

from __future__ import annotations

import re


def split_relalg_raw_parts(text: str) -> list[str]:
    """
    Split RelAlg text on top-level semicolons.

    Returns raw segments (comments and whitespace preserved). Empty/whitespace-only
    trailing segments after a final ``;`` are omitted.
    """
    text = text.replace("\r\n", "\n")
    if not text.strip():
        return []

    parts: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(text)
    depth_paren = depth_brace = depth_brack = 0
    in_single = in_double = False

    while i < n:
        ch = text[i]
        # line comment
        if (
            not in_single
            and not in_double
            and ch == "-"
            and i + 1 < n
            and text[i + 1] == "-"
        ):
            nl = text.find("\n", i)
            if nl < 0:
                buf.append(text[i:])
                break
            buf.append(text[i : nl + 1])
            i = nl + 1
            continue
        # block comment
        if (
            not in_single
            and not in_double
            and ch == "/"
            and i + 1 < n
            and text[i + 1] == "*"
        ):
            end = text.find("*/", i + 2)
            if end < 0:
                buf.append(text[i:])
                break
            buf.append(text[i : end + 2])
            i = end + 2
            continue
        if in_single:
            buf.append(ch)
            if ch == "'" and not (i + 1 < n and text[i + 1] == "'"):
                in_single = False
            elif ch == "'" and i + 1 < n and text[i + 1] == "'":
                buf.append(text[i + 1])
                i += 2
                continue
            i += 1
            continue
        if in_double:
            buf.append(ch)
            if ch == '"' and not (i > 0 and text[i - 1] == "\\"):
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue
        if ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren = max(0, depth_paren - 1)
        elif ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace = max(0, depth_brace - 1)
        elif ch == "[":
            depth_brack += 1
        elif ch == "]":
            depth_brack = max(0, depth_brack - 1)
        elif (
            ch == ";"
            and depth_paren == 0
            and depth_brace == 0
            and depth_brack == 0
        ):
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1

    tail = "".join(buf)
    if tail.strip():
        parts.append(tail)
    return parts


def peel_trailing_comments(text: str) -> tuple[str, str]:
    """
    Split ``text`` into ``(code, suffix)`` where ``suffix`` is trailing whitespace
    plus line/block comments after the last code character.
    """
    if not text:
        return "", ""

    i = 0
    n = len(text)
    last_code_end = 0
    in_single = in_double = False

    while i < n:
        ch = text[i]
        if (
            not in_single
            and not in_double
            and ch == "-"
            and i + 1 < n
            and text[i + 1] == "-"
        ):
            nl = text.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if (
            not in_single
            and not in_double
            and ch == "/"
            and i + 1 < n
            and text[i + 1] == "*"
        ):
            end = text.find("*/", i + 2)
            if end < 0:
                break
            i = end + 2
            continue
        if in_single:
            if ch == "'" and i + 1 < n and text[i + 1] == "'":
                last_code_end = i + 2
                i += 2
                continue
            last_code_end = i + 1
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            last_code_end = i + 1
            if ch == '"' and not (i > 0 and text[i - 1] == "\\"):
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            last_code_end = i + 1
            i += 1
            continue
        if ch == '"':
            in_double = True
            last_code_end = i + 1
            i += 1
            continue
        if ch.isspace():
            i += 1
            continue
        last_code_end = i + 1
        i += 1

    return text[:last_code_end], text[last_code_end:]


def peel_leading_comments(text: str) -> tuple[str, str]:
    """
    Split ``text`` into ``(prefix, rest)`` where ``prefix`` is leading whitespace
    and full-line / block comments before the first code character.
    """
    if not text:
        return "", ""

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "-" and i + 1 < n and text[i + 1] == "-":
            nl = text.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            if end < 0:
                return text, ""
            i = end + 2
            continue
        break
    return text[:i], text[i:]


def split_relalg_statements(text: str) -> list[tuple[str, str | None]]:
    """
    Split RelAlg text on top-level semicolons.

    Returns list of (statement_body, optional_label) where label is taken from
    a preceding `-- …` comment when present. Trailing/empty fragments are dropped.
    A query with no semicolons yields a single statement (backward compatible).
    Comment-only segments (e.g. a final ``;\\n-- note``) are skipped, not parsed.
    """
    parts = split_relalg_raw_parts(text)
    if not parts:
        return []

    # No semicolon at all → whole query is one statement
    if len(parts) == 1 and ";" not in text.replace("\r\n", "\n"):
        body, label = _strip_leading_comment_label(parts[0])
        if not body.strip() or _is_comment_only(body):
            return []
        return [(body, label)]

    results: list[tuple[str, str | None]] = []
    for part in parts:
        body, label = _strip_leading_comment_label(part)
        if not body.strip() or _is_comment_only(body):
            continue
        results.append((body.strip(), label))
    return results


def _is_comment_only(text: str) -> bool:
    """True when ``text`` has no RelAlg code (only whitespace / comments)."""
    _leading, rest = peel_leading_comments(text)
    code, _trailing = peel_trailing_comments(rest)
    return not code.strip()


_COMMENT_LABEL = re.compile(
    r"^\s*(?:--\s*(?P<label>[^\n]*?)(?:\n|$))+\s*(?P<body>[\s\S]*)$"
)


def _strip_leading_comment_label(part: str) -> tuple[str, str | None]:
    """Pull leading `--` comment lines into a label; leave the expression body."""
    m = _COMMENT_LABEL.match(part)
    if not m:
        return part.strip(), None
    labels = re.findall(r"--\s*([^\n]*)", part[: m.start("body")])
    label = None
    # Prefer the last non-empty comment as the short label
    for t in reversed(labels):
        t = t.strip()
        if t:
            label = t
            break
    return m.group("body").strip(), label
