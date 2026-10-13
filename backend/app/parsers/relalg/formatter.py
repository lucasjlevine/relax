from __future__ import annotations

from typing import Literal

from app.parsers.relalg import ast as ra

FormatStyle = Literal["pretty", "dense", "sparse"]

# Binary operator precedence (higher binds tighter). Joins > set ops.
_PREC_SET = 1
_PREC_JOIN = 2
# Loosest “parent” for a unary’s argument (inside op_{…}( … )).
_PREC_GROUP = 0


def _fmt_expr(node: object) -> str:
    if isinstance(node, ra.ColumnRef):
        if node.name == "*":
            return "*"
        if node.relation:
            return f"{node.relation}.{node.name}"
        return node.name
    if isinstance(node, ra.Literal):
        if node.value is None:
            return "null"
        if isinstance(node.value, str):
            return "'" + node.value.replace("'", "''") + "'"
        return str(node.value)
    if isinstance(node, ra.FuncCall):
        args = ", ".join(_fmt_expr(a) for a in node.args)
        return f"{node.name}({args})"
    if isinstance(node, ra.CaseExpr):
        parts = ["CASE"]
        for cond, result in node.whens:
            parts.append(f"WHEN {_fmt_expr(cond)} THEN {_fmt_expr(result)}")
        if node.else_result is not None:
            parts.append(f"ELSE {_fmt_expr(node.else_result)}")
        parts.append("END")
        return " ".join(parts)
    if isinstance(node, ra.BinaryExpr):
        op = {"and": "∧", "or": "∨", "!=": "≠", "<=": "≤", ">=": "≥"}.get(
            node.op, node.op
        )
        return f"{_fmt_expr(node.left)} {op} {_fmt_expr(node.right)}"
    if isinstance(node, ra.UnaryExpr):
        if node.op == "not":
            return f"¬{_fmt_expr(node.operand)}"
        return f"{node.op} {_fmt_expr(node.operand)}"
    return str(node)


def _indent(text: str, level: int) -> str:
    pad = "  " * level
    return "\n".join(pad + line if line else line for line in text.splitlines())


def _binary_prec(node: ra.RANode) -> int | None:
    if isinstance(node, (ra.Union, ra.Intersect, ra.Except)):
        return _PREC_SET
    if isinstance(
        node,
        (
            ra.Cross,
            ra.NaturalJoin,
            ra.Division,
            ra.ThetaJoin,
            ra.LeftOuterJoin,
            ra.RightOuterJoin,
            ra.FullOuterJoin,
            ra.LeftSemiJoin,
            ra.RightSemiJoin,
            ra.AntiJoin,
        ),
    ):
        return _PREC_JOIN
    return None


def _paren_binary(
    body: str,
    *,
    style: FormatStyle,
    node_prec: int,
    parent_prec: int | None,
    side: str | None,
) -> str:
    """Sparse always wraps binaries; pretty/dense omit implied parentheses."""
    if style == "sparse":
        return f"({body})"
    if parent_prec is None:
        return body
    if node_prec > parent_prec:
        return body
    if node_prec < parent_prec:
        return f"({body})"
    # Same precedence, left-associative: only the right child needs parens.
    return body if side == "left" else f"({body})"


def _break_binary(
    left: str,
    op: str,
    right: str,
    *,
    style: FormatStyle,
) -> bool:
    if style == "dense":
        return False
    if style == "sparse":
        return True
    # Pretty: break when already multiline or the joined line is long.
    if "\n" in left or "\n" in right:
        return True
    return len(left) + len(right) + len(op) > 88


def _break_unary(sub: str, child_s: str, *, style: FormatStyle) -> bool:
    if style == "dense":
        return False
    if style == "sparse":
        return True
    # Pretty: keep short unaries inline; expand when the argument is heavy.
    return "\n" in child_s or len(sub) > 64 or len(child_s) > 88


def format_relalg(
    node: ra.RANode,
    *,
    level: int = 0,
    style: FormatStyle = "pretty",
    parent_prec: int | None = None,
    side: str | None = None,
) -> str:
    """Pretty-print RelAlg using classical subscript notation."""
    dense = style == "dense"
    # Pretty/sparse omit outer parens on binaries inside op_{…}( … ).
    group_prec = None if style == "sparse" else _PREC_GROUP

    if isinstance(node, ra.Statement):
        parts: list[str] = []
        assigns = node.assignments or []
        for name, expr in assigns:
            body = format_relalg(expr, level=0, style=style)
            if not dense and "\n" in body:
                parts.append(f"{name} =\n{_indent(body, 1)}")
            else:
                parts.append(f"{name} = {body}")
        # If result is just the last assignment name, omit a redundant trailing line.
        if (
            assigns
            and isinstance(node.result, ra.Relation)
            and node.result.name == assigns[-1][0]
        ):
            return ("\n" if dense else "\n\n").join(parts)
        result_s = format_relalg(node.result, level=0, style=style)
        if parts:
            sep = "\n" if dense else "\n\n"
            return sep.join(parts) + sep + result_s
        return result_s

    def wrap_sub(op: str, sub: str, child: ra.RANode) -> str:
        child_s = format_relalg(
            child,
            level=level + 1,
            style=style,
            parent_prec=group_prec,
        )
        if _break_unary(sub, child_s, style=style):
            return f"{op}_{{{sub}}}(\n{_indent(child_s, 1)}\n)"
        return f"{op}_{{{sub}}}({child_s})"

    if isinstance(node, ra.Relation):
        return node.name

    if isinstance(node, ra.Projection):
        cols = ", ".join(
            _fmt_expr(e) + (f"→{a}" if a else "") for e, a in node.items
        )
        return wrap_sub("π", cols, node.child)

    if isinstance(node, ra.Selection):
        return wrap_sub("σ", _fmt_expr(node.condition), node.child)

    if isinstance(node, ra.RenameRelation):
        return wrap_sub("ρ", node.new_name, node.child)

    if isinstance(node, ra.RenameColumns):
        mapping = ", ".join(f"{a}→{b}" for a, b in node.mapping)
        return wrap_sub("ρ", mapping, node.child)

    if isinstance(node, ra.OrderBy):
        keys = ", ".join(
            f"{_fmt_expr(e)} {d}" for e, d in node.keys
        )
        return wrap_sub("τ", keys, node.child)

    if isinstance(node, ra.GroupBy):
        parts = [_fmt_expr(c) for c in node.group_cols]
        aggs = [
            f"{fn}({_fmt_expr(arg)})" + (f"→{alias}" if alias else "")
            for fn, arg, alias in node.aggregates
        ]
        sub = ", ".join(parts)
        if aggs:
            sub = (sub + "; " if sub else "") + ", ".join(aggs)
        return wrap_sub("γ", sub, node.child)

    if isinstance(node, ra.Distinct):
        child_s = format_relalg(
            node.child,
            level=level + 1,
            style=style,
            parent_prec=group_prec,
        )
        if style != "dense" and ("\n" in child_s or style == "sparse"):
            return f"δ(\n{_indent(child_s, 1)}\n)"
        return f"δ({child_s})"

    binary_ops = {
        ra.Union: "∪",
        ra.Intersect: "∩",
        ra.Except: "−",
        ra.Cross: "×",
        ra.NaturalJoin: "⋈",
        ra.Division: "÷",
    }
    for cls, sym in binary_ops.items():
        if isinstance(node, cls):
            prec = _binary_prec(node) or _PREC_JOIN
            left = format_relalg(
                node.left, level=level + 1, style=style, parent_prec=prec, side="left"
            )
            right = format_relalg(
                node.right, level=level + 1, style=style, parent_prec=prec, side="right"
            )
            if _break_binary(left, sym, right, style=style):
                body = f"{left}\n  {sym}\n{right}"
                wrapped = _paren_binary(
                    body,
                    style=style,
                    node_prec=prec,
                    parent_prec=parent_prec,
                    side=side,
                )
                if wrapped.startswith("(") and "\n" in wrapped:
                    # Expand parentheses around a multiline binary.
                    inner = wrapped[1:-1] if wrapped.endswith(")") else wrapped
                    return f"(\n{_indent(inner, 1)}\n)"
                return wrapped
            body = f"{left} {sym} {right}"
            return _paren_binary(
                body,
                style=style,
                node_prec=prec,
                parent_prec=parent_prec,
                side=side,
            )

    join_map = [
        (ra.ThetaJoin, "⋈"),
        (ra.LeftOuterJoin, "⟕"),
        (ra.RightOuterJoin, "⟖"),
        (ra.FullOuterJoin, "⟗"),
        (ra.LeftSemiJoin, "⋉"),
        (ra.RightSemiJoin, "⋊"),
        (ra.AntiJoin, "▷"),
    ]
    for cls, sym in join_map:
        if isinstance(node, cls):
            prec = _PREC_JOIN
            left = format_relalg(
                node.left, level=level + 1, style=style, parent_prec=prec, side="left"
            )
            right = format_relalg(
                node.right, level=level + 1, style=style, parent_prec=prec, side="right"
            )
            cond = getattr(node, "condition", None)
            op = f"{sym}_{{{_fmt_expr(cond)}}}" if cond is not None else sym
            if _break_binary(left, op, right, style=style):
                body = f"{left}\n  {op}\n{right}"
                wrapped = _paren_binary(
                    body,
                    style=style,
                    node_prec=prec,
                    parent_prec=parent_prec,
                    side=side,
                )
                if wrapped.startswith("(") and "\n" in wrapped:
                    inner = wrapped[1:-1] if wrapped.endswith(")") else wrapped
                    return f"(\n{_indent(inner, 1)}\n)"
                return wrapped
            body = f"{left} {op} {right}"
            return _paren_binary(
                body,
                style=style,
                node_prec=prec,
                parent_prec=parent_prec,
                side=side,
            )

    return str(node)


def _normalize_leading_comments(leading: str) -> str:
    """Drop blank lines around leading comments; end with a single newline."""
    if not leading.strip():
        return ""
    return leading.strip("\n") + "\n"


def _normalize_trailing_comments(trailing: str) -> str:
    """
    Keep inline `` -- note`` as a single-space prefix; put line/block comments
    on the next line with exactly one leading newline.
    """
    if not trailing.strip():
        return ""
    # Same-line trailing comment (space then -- or /*)
    rest = trailing.lstrip(" \t")
    if trailing[:1] in " \t" and not rest.startswith("\n"):
        return " " + rest.lstrip()
    return "\n" + trailing.lstrip()


def format_relalg_query(query: str, *, style: FormatStyle = "pretty") -> str:
    from app.parsers.relalg.parser import parse_relalg
    from app.parsers.relalg.statements import (
        peel_leading_comments,
        peel_trailing_comments,
        split_relalg_raw_parts,
    )

    text = query.replace("\r\n", "\n")
    parts = split_relalg_raw_parts(text)
    if not parts:
        return ""

    multi = len(parts) > 1 or ";" in text
    chunks: list[str] = []
    for part in parts:
        if not part.strip():
            continue
        leading, rest = peel_leading_comments(part)
        code, trailing = peel_trailing_comments(rest)
        lead = _normalize_leading_comments(leading)
        trail = _normalize_trailing_comments(trailing)
        if not code.strip():
            # Comment-only segment (e.g. after a final `;`) — keep comments only.
            chunks.append(part.strip())
            continue
        formatted = format_relalg(parse_relalg(code), style=style)
        if multi:
            piece = f"{lead}{formatted};{trail}"
        else:
            piece = f"{lead}{formatted}{trail}"
        chunks.append(piece)
    if not multi:
        return chunks[0]
    # Always separate statements with a blank line (including dense).
    return "\n\n".join(c.rstrip("\n") for c in chunks)
