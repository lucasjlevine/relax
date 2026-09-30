import {
  Decoration,
  type DecorationSet,
  EditorView,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import { RangeSetBuilder, StateField } from "@codemirror/state";

export type SchemaHint = {
  relations: { name: string; columns: { name: string; type: string }[] }[];
};

export type CursorZone = {
  kind: "main" | "subscript" | "before-subscript" | "after-subscript";
  /** Short badge text shown in the UI */
  badge: string;
  /** Longer explanation for title/tooltip */
  label: string;
  content?: string;
  line: number;
  column: number;
};

type SubscriptSpan = {
  from: number;
  innerFrom: number;
  innerTo: number;
  to: number;
  content: string;
  operator: string;
  role: string;
};

const OP_META: { re: RegExp; symbol: string; role: string }[] = [
  { re: /π|pi\b/i, symbol: "π", role: "projection columns" },
  { re: /σ|sigma\b/i, symbol: "σ", role: "selection condition" },
  { re: /ρ|rho\b/i, symbol: "ρ", role: "rename mapping" },
  { re: /γ|gamma\b|group\s+by/i, symbol: "γ", role: "group / aggregates" },
  { re: /τ|tau\b|order\s+by|sort\b/i, symbol: "τ", role: "sort keys" },
  { re: /⋈|join\b/i, symbol: "⋈", role: "join condition" },
  { re: /⟕|left\s+join/i, symbol: "⟕", role: "left-join condition" },
  { re: /⟖|right\s+join/i, symbol: "⟖", role: "right-join condition" },
  { re: /⟗|full\s+join/i, symbol: "⟗", role: "full-join condition" },
];

const OP_SYMBOLS =
  /^(π|σ|ρ|τ|γ|δ|⋈|⟕|⟖|⟗|⋉|⋊|▷|∪|∩|−|×|÷|pi|sigma|rho|tau|gamma|delta|join|union|intersect|except|cross|division)$/i;

const HELPER_NAMES = new Set(
  [
    "rownum",
    "row_number",
    "rand",
    "length",
    "strlen",
    "upper",
    "ucase",
    "lower",
    "lcase",
    "concat",
    "date",
    "adddate",
    "subdate",
    "year",
    "month",
    "day",
    "dayofmonth",
    "hour",
    "minute",
    "second",
    "now",
    "abs",
    "round",
    "floor",
    "ceil",
    "ceiling",
    "coalesce",
    "add",
    "sub",
    "mul",
    "div",
    "mod",
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "case",
  ].map((s) => s.toLowerCase()),
);

function operatorBefore(text: string, index: number): { symbol: string; role: string } {
  const ahead = text.slice(Math.max(0, index - 24), index);
  for (const op of OP_META) {
    if (op.re.test(ahead)) return { symbol: op.symbol, role: op.role };
  }
  return { symbol: "_{}", role: "subscript" };
}

function findSubscripts(text: string): SubscriptSpan[] {
  const spans: SubscriptSpan[] = [];
  const re = /_\{([^{}]*)\}/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text))) {
    const from = match.index;
    const to = from + match[0].length;
    const meta = operatorBefore(text, from);
    spans.push({
      from,
      innerFrom: from + 2,
      innerTo: to - 1,
      to,
      content: match[1] ?? "",
      operator: meta.symbol,
      role: meta.role,
    });
  }
  return spans;
}

function summarizeContent(content: string, max = 28): string {
  const t = content.trim().replace(/\s+/g, " ");
  if (!t) return "empty";
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

function tokenAt(text: string, pos: number): string | null {
  const left = text.slice(0, pos);
  const right = text.slice(pos);
  const pre = left.match(/[A-Za-z_πσρτγδ⋈∪∩×÷][\w.πσρτγδ⋈∪∩×÷]*$/u);
  const post = right.match(/^[A-Za-z_πσρτγδ⋈∪∩×÷][\w.πσρτγδ⋈∪∩×÷]*/u);
  // Also single unicode op under cursor
  if (!pre && !post) {
    const ch = text[pos] ?? text[pos - 1];
    if (ch && OP_SYMBOLS.test(ch)) return ch;
    return null;
  }
  const tok = `${pre?.[0] ?? ""}${post?.[0] ?? ""}`;
  return tok || null;
}

function lineCol(text: string, pos: number): { line: number; column: number } {
  const clamped = Math.max(0, Math.min(pos, text.length));
  const before = text.slice(0, clamped);
  const lines = before.split("\n");
  return { line: lines.length, column: (lines[lines.length - 1]?.length ?? 0) + 1 };
}

function classifyMainToken(
  tok: string,
  schema: SchemaHint | null | undefined,
): { badge: string; label: string } {
  if (OP_SYMBOLS.test(tok)) {
    return {
      badge: `Operator ${tok}`,
      label: `RelAlg operator “${tok}”`,
    };
  }
  const lower = tok.toLowerCase();
  if (HELPER_NAMES.has(lower) || HELPER_NAMES.has(lower.split(".")[0] ?? "")) {
    return {
      badge: `Function ${tok}`,
      label: `Helper function “${tok}”`,
    };
  }
  if (tok.includes(".")) {
    const [rel, col] = tok.split(".", 2);
    return {
      badge: `Attribute ${tok}`,
      label: `Qualified attribute “${col}” on relation “${rel}”`,
    };
  }
  if (schema) {
    const rel = schema.relations.find(
      (r) => r.name.toLowerCase() === lower,
    );
    if (rel) {
      return {
        badge: `Relation ${rel.name}`,
        label: `Relation “${rel.name}” from the current dataset`,
      };
    }
    for (const r of schema.relations) {
      const col = r.columns.find((c) => c.name.toLowerCase() === lower);
      if (col) {
        return {
          badge: `Attribute ${col.name}`,
          label: `Attribute “${col.name}” (${col.type}) on ${r.name}`,
        };
      }
    }
  }
  return {
    badge: `Main · ${tok}`,
    label: `At name “${tok}” (relation, attribute, or function)`,
  };
}

function zoneForPos(
  pos: number,
  text: string,
  spans: SubscriptSpan[],
  schema?: SchemaHint | null,
): CursorZone {
  const { line, column } = lineCol(text, pos);
  const loc = `${line}:${column}`;

  for (const s of spans) {
    const preview = summarizeContent(s.content);
    if (pos === s.from || (pos > s.from && pos <= s.innerFrom)) {
      return {
        kind: "before-subscript",
        badge: `${loc} · ${s.operator} · open`,
        label: `Line ${line}, column ${column} — just before ${s.role} (${preview})`,
        content: s.content,
        line,
        column,
      };
    }
    if (pos === s.to || (pos >= s.innerTo && pos < s.to)) {
      return {
        kind: "after-subscript",
        badge: `${loc} · ${s.operator} · close`,
        label: `Line ${line}, column ${column} — just after ${s.role} (${preview})`,
        content: s.content,
        line,
        column,
      };
    }
    if (pos > s.innerFrom && pos < s.innerTo) {
      return {
        kind: "subscript",
        badge: `${loc} · ${s.operator} · ${s.role}`,
        label: `Line ${line}, column ${column} — editing ${s.role}: ${preview}`,
        content: s.content,
        line,
        column,
      };
    }
  }

  const tok = tokenAt(text, pos);
  if (tok) {
    const classified = classifyMainToken(tok, schema);
    return {
      kind: "main",
      badge: `${loc} · ${classified.badge}`,
      label: `Line ${line}, column ${column} — ${classified.label}`,
      line,
      column,
    };
  }
  return {
    kind: "main",
    badge: `${loc} · Main expression`,
    label: `Line ${line}, column ${column} — outside any subscript`,
    line,
    column,
  };
}

/** Cursor zone derived from doc + selection (no effects / no feedback loops). */
export const cursorZoneField = StateField.define<CursorZone>({
  create(state) {
    const text = state.doc.toString();
    return zoneForPos(
      state.selection.main.head,
      text,
      findSubscripts(text),
    );
  },
  update(value, tr) {
    if (tr.docChanged || tr.selection) {
      const text = tr.state.doc.toString();
      return zoneForPos(
        tr.state.selection.main.head,
        text,
        findSubscripts(text),
      );
    }
    return value;
  },
});

function activeSpanIndex(pos: number, spans: SubscriptSpan[]): number {
  return spans.findIndex((s) => pos >= s.from && pos <= s.to);
}

function buildDecorations(view: EditorView): DecorationSet {
  const text = view.state.doc.toString();
  const spans = findSubscripts(text);
  const pos = view.state.selection.main.head;
  const active = activeSpanIndex(pos, spans);
  const builder = new RangeSetBuilder<Decoration>();

  type Mark = { from: number; to: number; className: string };
  const marks: Mark[] = [];

  spans.forEach((s, i) => {
    const editing = i === active;
    if (editing) {
      marks.push({
        from: s.from,
        to: s.innerFrom,
        className: "cm-sub-cluster-active cm-sub-marker-visible",
      });
      if (s.innerTo > s.innerFrom) {
        marks.push({
          from: s.innerFrom,
          to: s.innerTo,
          className: "cm-sub-cluster-active cm-relalg-sub-active",
        });
      }
      marks.push({
        from: s.innerTo,
        to: s.to,
        className: "cm-sub-cluster-active cm-sub-marker-visible",
      });
    } else {
      marks.push({
        from: s.from,
        to: s.innerFrom,
        className: "cm-sub-marker-hidden",
      });
      if (s.innerTo > s.innerFrom) {
        marks.push({
          from: s.innerFrom,
          to: s.innerTo,
          className: "cm-relalg-sub",
        });
      }
      marks.push({
        from: s.innerTo,
        to: s.to,
        className: "cm-sub-marker-hidden",
      });
    }
  });

  marks.sort((a, b) => a.from - b.from || a.to - b.to);
  for (const m of marks) {
    if (m.to > m.from) {
      builder.add(m.from, m.to, Decoration.mark({ class: m.className }));
    }
  }
  return builder.finish();
}

export function createRelalgSubscriptExtension(
  onZoneChange?: (zone: CursorZone) => void,
  getSchema?: () => SchemaHint | null,
) {
  const computeZone = (view: EditorView): CursorZone => {
    const text = view.state.doc.toString();
    return zoneForPos(
      view.state.selection.main.head,
      text,
      findSubscripts(text),
      getSchema?.() ?? null,
    );
  };

  return [
    cursorZoneField,
    ViewPlugin.fromClass(
      class {
        decorations: DecorationSet;
        constructor(view: EditorView) {
          this.decorations = buildDecorations(view);
          queueMicrotask(() => onZoneChange?.(computeZone(view)));
        }
        update(update: ViewUpdate) {
          if (update.docChanged || update.selectionSet || update.viewportChanged) {
            this.decorations = buildDecorations(update.view);
          }
          if (update.docChanged || update.selectionSet) {
            onZoneChange?.(computeZone(update.view));
          }
        }
      },
      { decorations: (v) => v.decorations },
    ),
    EditorView.theme({
      "&.cm-focused .cm-cursor": {
        borderLeftWidth: "2px",
        borderLeftColor: "#0f6a7c",
      },
      ".cm-sub-cluster-active": {
        backgroundColor: "rgba(15, 106, 124, 0.14)",
        borderRadius: "3px",
        boxShadow: "inset 0 0 0 1px rgba(15, 106, 124, 0.35)",
      },
      ".cm-sub-marker-hidden": {
        opacity: "0.2",
        fontSize: "0.6em",
        verticalAlign: "sub",
        color: "#64748b",
      },
      ".cm-sub-marker-visible": {
        opacity: "1",
        fontSize: "0.9em",
        fontWeight: "700",
        color: "#0f6a7c",
        letterSpacing: "0.02em",
      },
      ".cm-relalg-sub": {
        fontSize: "0.72em",
        verticalAlign: "sub",
        lineHeight: "1",
      },
      ".cm-relalg-sub-active": {
        fontSize: "0.95em",
        verticalAlign: "baseline",
        fontWeight: "600",
        color: "#0f3d48",
        backgroundColor: "rgba(255, 255, 255, 0.7)",
        borderRadius: "2px",
        padding: "0 2px",
      },
    }),
  ];
}
