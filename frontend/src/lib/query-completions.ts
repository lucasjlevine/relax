import {
  autocompletion,
  type Completion,
  type CompletionContext,
  type CompletionResult,
} from "@codemirror/autocomplete";
import type { EditorView } from "@codemirror/view";

export type SchemaHint = {
  relations: { name: string; columns: { name: string; type: string }[] }[];
};

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

export function createSchemaCompletions(getSchema: () => SchemaHint | null) {
  return autocompletion({
    override: [
      (context: CompletionContext): CompletionResult | null => {
        const word = context.matchBefore(/[A-Za-z_][\w.]*/);
        if (!word || (word.from === word.to && !context.explicit)) return null;
        const typed = word.text;
        const schema = getSchema();
        const options: Completion[] = [];

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
                options.push({
                  label: `${rel.name}.${col.name}`,
                  type: "property",
                  detail: col.type,
                  boost: 12,
                });
              }
            }
            if (options.length) {
              return {
                from: word.from,
                options,
                validFor: /^[\w.]*$/,
              };
            }
          }
        }

        if (schema) {
          for (const rel of schema.relations) {
            options.push({
              label: rel.name,
              type: "class",
              detail: "relation",
              boost: 10,
            });
            for (const col of rel.columns) {
              options.push({
                label: col.name,
                type: "property",
                detail: `${rel.name} · ${col.type}`,
                boost: 5,
              });
              options.push({
                label: `${rel.name}.${col.name}`,
                type: "property",
                detail: col.type,
                boost: 8,
              });
            }
          }
        }

        for (const fn of HELPER_FNS) {
          options.push({
            label: fn.label,
            type: "function",
            detail: fn.detail,
            apply: insertWithCursorInParens(fn.apply),
            boost: 3,
          });
        }

        const lower = typed.toLowerCase();
        const filtered = options.filter((o) =>
          o.label.toLowerCase().includes(lower),
        );
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
