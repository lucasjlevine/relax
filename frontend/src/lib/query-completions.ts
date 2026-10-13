import {
  acceptCompletion,
  autocompletion,
  type Completion,
  type CompletionContext,
  type CompletionResult,
} from "@codemirror/autocomplete";
import { keymap } from "@codemirror/view";
import { Prec } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";

export type SchemaHint = {
  relations: { name: string; columns: { name: string; type: string }[] }[];
};

function insertWithCursor(snippet: string, cursorOffset: number) {
  return (
    view: EditorView,
    _completion: Completion,
    from: number,
    to: number,
  ) => {
    view.dispatch({
      changes: { from, to, insert: snippet },
      selection: { anchor: from + cursorOffset },
    });
  };
}

function insertWithCursorInParens(snippet: string) {
  return (
    view: EditorView,
    _completion: Completion,
    from: number,
    to: number,
  ) => {
    const open = snippet.indexOf("(");
    const close = snippet.lastIndexOf(")");
    let anchor = from + snippet.length;
    if (open >= 0 && close > open) {
      anchor = from + open + 1;
    } else if (snippet.startsWith("CASE WHEN")) {
      anchor = from + "CASE WHEN ".length;
    }
    view.dispatch({
      changes: { from, to, insert: snippet },
      selection: { anchor },
    });
  };
}

const HELPER_FNS: { label: string; detail: string; apply: string }[] = [
  { label: "rownum()", detail: "0-based row index", apply: "rownum()" },
  { label: "rand()", detail: "random [0,1]", apply: "rand()" },
  { label: "length()", detail: "string length", apply: "length()" },
  { label: "upper()", detail: "uppercase", apply: "upper()" },
  { label: "lower()", detail: "lowercase", apply: "lower()" },
  { label: "concat()", detail: "concatenate strings", apply: "concat()" },
  { label: "date()", detail: "parse YYYY-MM-DD", apply: "date()" },
  { label: "year()", detail: "extract year", apply: "year()" },
  { label: "month()", detail: "extract month 1–12", apply: "month()" },
  { label: "day()", detail: "extract day of month", apply: "day()" },
  { label: "adddate()", detail: "date + days", apply: "adddate()" },
  { label: "subdate()", detail: "date − days", apply: "subdate()" },
  { label: "now()", detail: "current timestamp", apply: "now()" },
  { label: "abs()", detail: "absolute value", apply: "abs()" },
  { label: "round()", detail: "round number", apply: "round()" },
  { label: "floor()", detail: "floor", apply: "floor()" },
  { label: "ceil()", detail: "ceiling", apply: "ceil()" },
  { label: "coalesce()", detail: "first non-null", apply: "coalesce()" },
  { label: "mod()", detail: "modulo", apply: "mod()" },
  {
    label: "CASE WHEN",
    detail: "conditional expression",
    apply: "CASE WHEN  THEN  END",
  },
];

/** Plaintext / keyword triggers that insert classical RelAlg symbols. */
const RELALG_OPS: {
  label: string;
  detail: string;
  apply: string;
  cursorOffset?: number;
  aliases: string[];
  boost?: number;
}[] = [
  {
    label: "π",
    detail: "projection",
    apply: "π_{}()",
    cursorOffset: 3,
    aliases: ["pi", "project", "projection"],
    boost: 20,
  },
  {
    label: "σ",
    detail: "selection",
    apply: "σ_{}()",
    cursorOffset: 3,
    aliases: ["sigma", "selection"],
    boost: 20,
  },
  {
    label: "ρ",
    detail: "rename",
    apply: "ρ_{}()",
    cursorOffset: 3,
    aliases: ["rho", "rename"],
    boost: 18,
  },
  {
    label: "τ",
    detail: "order by",
    apply: "τ_{}()",
    cursorOffset: 3,
    aliases: ["tau", "order", "sort"],
    boost: 18,
  },
  {
    label: "γ",
    detail: "group by",
    apply: "γ_{}()",
    cursorOffset: 3,
    aliases: ["gamma", "group"],
    boost: 18,
  },
  {
    label: "δ",
    detail: "duplicate elimination",
    apply: "δ()",
    cursorOffset: 2,
    aliases: ["delta", "distinct"],
    boost: 18,
  },
  {
    label: "⋈",
    detail: "natural join",
    apply: " ⋈ ",
    aliases: ["join"],
    boost: 19,
  },
  {
    label: "⋈θ",
    detail: "theta join",
    apply: " ⋈_{} ",
    cursorOffset: 4,
    aliases: ["theta"],
    boost: 17,
  },
  {
    label: "⟕",
    detail: "left outer join",
    apply: " ⟕ ",
    aliases: ["left"],
    boost: 17,
  },
  {
    label: "⟖",
    detail: "right outer join",
    apply: " ⟖ ",
    aliases: ["right"],
    boost: 17,
  },
  {
    label: "⟗",
    detail: "full outer join",
    apply: " ⟗ ",
    aliases: ["full"],
    boost: 17,
  },
  {
    label: "⋉",
    detail: "left semi-join",
    apply: " ⋉ ",
    aliases: ["semi", "semijoin"],
    boost: 16,
  },
  {
    label: "▷",
    detail: "anti-join",
    apply: " ▷ ",
    aliases: ["anti", "antijoin"],
    boost: 16,
  },
  {
    label: "∪",
    detail: "union",
    apply: " ∪ ",
    aliases: ["union"],
    boost: 16,
  },
  {
    label: "∩",
    detail: "intersection",
    apply: " ∩ ",
    aliases: ["intersect", "intersection"],
    boost: 16,
  },
  {
    label: "−",
    detail: "set difference",
    apply: " − ",
    aliases: ["except", "minus", "difference"],
    boost: 16,
  },
  {
    label: "×",
    detail: "cross product",
    apply: " × ",
    aliases: ["cross"],
    boost: 16,
  },
  {
    label: "÷",
    detail: "division",
    apply: " ÷ ",
    aliases: ["division"],
    boost: 16,
  },
  {
    label: "∧",
    detail: "logical and",
    apply: " ∧ ",
    aliases: ["and"],
    boost: 12,
  },
  {
    label: "∨",
    detail: "logical or",
    apply: " ∨ ",
    aliases: ["or"],
    boost: 12,
  },
  {
    label: "¬",
    detail: "logical not",
    apply: "¬",
    aliases: ["not"],
    boost: 12,
  },
];

function matchesOp(
  typed: string,
  op: (typeof RELALG_OPS)[number],
): boolean {
  const lower = typed.toLowerCase();
  if (!lower) return false;
  if (op.label.toLowerCase().startsWith(lower)) return true;
  return op.aliases.some((a) => a.startsWith(lower));
}

/** Tab accepts an active completion; otherwise falls through to indent. */
export const tabAcceptCompletion = Prec.highest(
  keymap.of([{ key: "Tab", run: acceptCompletion }]),
);

export function createSchemaCompletions(
  getSchema: () => SchemaHint | null,
  options?: { relalgOps?: boolean },
) {
  const includeOps = options?.relalgOps ?? false;
  return autocompletion({
    override: [
      (context: CompletionContext): CompletionResult | null => {
        const word = context.matchBefore(/[A-Za-z_][\w.]*/);
        if (!word || (word.from === word.to && !context.explicit)) return null;
        const typed = word.text;
        const schema = getSchema();
        const optionsList: Completion[] = [];

        // Relation. → attributes of that relation only
        const dotted = typed.match(/^([A-Za-z_][\w]*)\.(.*)$/);
        if (dotted && schema) {
          const relName = dotted[1];
          const partial = dotted[2] ?? "";
          const rel = schema.relations.find(
            (r) => r.name.toLowerCase() === relName.toLowerCase(),
          );
          if (rel) {
            for (const col of rel.columns) {
              if (
                !partial ||
                col.name.toLowerCase().startsWith(partial.toLowerCase())
              ) {
                optionsList.push({
                  label: `${rel.name}.${col.name}`,
                  type: "property",
                  detail: col.type,
                  boost: 12,
                });
              }
            }
            if (optionsList.length) {
              return {
                from: word.from,
                options: optionsList,
                validFor: /^[\w.]*$/,
              };
            }
          }
        }

        if (includeOps) {
          for (const op of RELALG_OPS) {
            if (!matchesOp(typed, op)) continue;
            const cursor =
              op.cursorOffset !== undefined
                ? insertWithCursor(op.apply, op.cursorOffset)
                : op.apply;
            optionsList.push({
              label: op.label,
              type: "keyword",
              detail: op.detail,
              boost: op.boost ?? 15,
              apply: cursor,
            });
            // Also surface under the typed alias so the popup shows why it matched.
            for (const alias of op.aliases) {
              if (
                alias.toLowerCase().startsWith(typed.toLowerCase()) &&
                alias !== op.label
              ) {
                optionsList.push({
                  label: alias,
                  type: "keyword",
                  detail: `→ ${op.label} ${op.detail}`,
                  boost: (op.boost ?? 15) - 1,
                  apply:
                    op.cursorOffset !== undefined
                      ? insertWithCursor(op.apply, op.cursorOffset)
                      : op.apply,
                });
              }
            }
          }
        }

        if (schema) {
          for (const rel of schema.relations) {
            optionsList.push({
              label: rel.name,
              type: "class",
              detail: "relation",
              boost: 10,
            });
            for (const col of rel.columns) {
              optionsList.push({
                label: col.name,
                type: "property",
                detail: `${rel.name} · ${col.type}`,
                boost: 5,
              });
              optionsList.push({
                label: `${rel.name}.${col.name}`,
                type: "property",
                detail: col.type,
                boost: 8,
              });
            }
          }
        }

        for (const fn of HELPER_FNS) {
          optionsList.push({
            label: fn.label,
            type: "function",
            detail: fn.detail,
            apply: insertWithCursorInParens(fn.apply),
            boost: 3,
          });
        }

        const lower = typed.toLowerCase();
        const filtered = optionsList.filter((o) => {
          if (o.type === "keyword") return true; // already matched aliases
          return o.label.toLowerCase().includes(lower);
        });
        if (!filtered.length) return null;
        return {
          from: word.from,
          options: filtered,
          validFor: /^[\w.]*$/,
        };
      },
    ],
  });
}
