import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";
import { EditorView } from "@codemirror/view";

/** Calm teal/slate highlighting that fits the calculator chrome. */
const editorHighlightStyle = HighlightStyle.define([
  { tag: t.keyword, color: "#0f6a7c", fontWeight: "600" },
  { tag: t.standard(t.function(t.variableName)), color: "#0b5f4a" },
  { tag: t.function(t.variableName), color: "#0b5f4a" },
  { tag: t.string, color: "#9a3412" },
  { tag: t.number, color: "#1d4ed8" },
  { tag: t.comment, color: "#64748b", fontStyle: "italic" },
  { tag: t.operator, color: "#475569" },
  { tag: t.bracket, color: "#334155" },
  { tag: t.variableName, color: "#0f172a" },
  { tag: t.typeName, color: "#0f6a7c" },
  { tag: t.bool, color: "#1d4ed8" },
  { tag: t.null, color: "#1d4ed8", fontWeight: "600" },
  { tag: t.propertyName, color: "#0f3d48" },
  { tag: t.punctuation, color: "#64748b" },
]);

export const editorHighlight = [
  syntaxHighlighting(editorHighlightStyle),
  EditorView.theme({
    "&": { backgroundColor: "transparent" },
    ".cm-content": { caretColor: "#0f6a7c" },
    "&.cm-focused .cm-cursor": { borderLeftColor: "#0f6a7c" },
    ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": {
      backgroundColor: "rgba(15, 106, 124, 0.18)",
    },
    ".cm-activeLine": { backgroundColor: "rgba(15, 106, 124, 0.05)" },
    ".cm-gutters": {
      backgroundColor: "transparent",
      color: "#94a3b8",
      border: "none",
    },
    ".cm-activeLineGutter": { backgroundColor: "transparent", color: "#0f6a7c" },
  }),
];
