from __future__ import annotations

from app.parsers.relalg import ast as ra


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


def format_relalg(node: ra.RANode, *, level: int = 0, multiline: bool = True) -> str:
    """Pretty-print RelAlg using classical subscript notation."""

    if isinstance(node, ra.Statement):
        parts: list[str] = []
        assigns = node.assignments or []
        for name, expr in assigns:
            body = format_relalg(expr, level=0, multiline=multiline)
            if "\n" in body:
                parts.append(f"{name} =\n{_indent(body, 1)}")
            else:
                parts.append(f"{name} = {body}")
        # If result is just the last assignment name, omit a redundant trailing line.
        if (
            assigns
            and isinstance(node.result, ra.Relation)
            and node.result.name == assigns[-1][0]
        ):
            return "\n\n".join(parts)
        result_s = format_relalg(node.result, level=0, multiline=multiline)
        if parts:
            return "\n\n".join(parts) + "\n\n" + result_s
        return result_s

    def wrap_sub(op: str, sub: str, child: ra.RANode) -> str:
        child_s = format_relalg(child, level=level + 1, multiline=multiline)
        if multiline and ("\n" in child_s or len(sub) > 40):
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
        child_s = format_relalg(node.child, level=level + 1, multiline=multiline)
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
            left = format_relalg(node.left, level=level + 1, multiline=multiline)
            right = format_relalg(node.right, level=level + 1, multiline=multiline)
            if multiline and ("\n" in left or "\n" in right):
                return f"(\n{_indent(left, 1)}\n  {sym}\n{_indent(right, 1)}\n)"
            return f"({left} {sym} {right})"

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
            left = format_relalg(node.left, level=level + 1, multiline=multiline)
            right = format_relalg(node.right, level=level + 1, multiline=multiline)
            cond = getattr(node, "condition", None)
            op = f"{sym}_{{{_fmt_expr(cond)}}}" if cond is not None else sym
            if multiline and ("\n" in left or "\n" in right):
                return f"(\n{_indent(left, 1)}\n  {op}\n{_indent(right, 1)}\n)"
            return f"({left} {op} {right})"

    return str(node)


def format_relalg_query(query: str) -> str:
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
        if not code.strip():
            # Comment-only segment (e.g. after a final `;`) — keep as-is.
            chunks.append(part.strip("\n"))
            continue
        formatted = format_relalg(parse_relalg(code))
        if multi and trailing.strip():
            # Place `;` after the expression, before trailing comments.
            lead = ""
            if leading:
                lead = leading if leading.endswith("\n") else leading + "\n"
            piece = f"{lead}{formatted};{trailing}"
        elif multi:
            lead = ""
            if leading:
                lead = leading if leading.endswith("\n") else leading + "\n"
            piece = f"{lead}{formatted}{trailing}".rstrip() + ";"
        else:
            lead = ""
            if leading:
                lead = leading if leading.endswith("\n") else leading + "\n"
            piece = f"{lead}{formatted}{trailing}"
        chunks.append(piece)
    return "\n\n".join(chunks) if multi else chunks[0]
