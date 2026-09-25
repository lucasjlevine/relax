import {
  Decoration,
  type DecorationSet,
  EditorView,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import { RangeSetBuilder } from "@codemirror/state";

type Span = { from: number; to: number; className: string };

/**
 * Visually render `_{args}` as in-line subscripts while keeping source editable.
 * Markers `_{` / `}` are visually suppressed; inner text is subscript-styled.
 */
function collectSpans(text: string): Span[] {
  const spans: Span[] = [];
  const re = /_\{([^{}]*)\}/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text))) {
    const from = match.index;
    const innerFrom = from + 2;
    const innerTo = from + match[0].length - 1;
    const to = from + match[0].length;
    spans.push({ from, to: innerFrom, className: "cm-sub-marker" });
    if (innerTo > innerFrom) {
      spans.push({ from: innerFrom, to: innerTo, className: "cm-relalg-sub" });
    }
    spans.push({ from: innerTo, to, className: "cm-sub-marker" });
  }
  spans.sort((a, b) => a.from - b.from || a.to - b.to);
  return spans;
}

function buildDecorations(view: EditorView): DecorationSet {
  const builder = new RangeSetBuilder<Decoration>();
  for (const span of collectSpans(view.state.doc.toString())) {
    builder.add(span.from, span.to, Decoration.mark({ class: span.className }));
  }
  return builder.finish();
}

export const relalgSubscriptExtension = [
  ViewPlugin.fromClass(
    class {
      decorations: DecorationSet;
      constructor(view: EditorView) {
        this.decorations = buildDecorations(view);
      }
      update(update: ViewUpdate) {
        if (update.docChanged || update.viewportChanged) {
          this.decorations = buildDecorations(update.view);
        }
      }
    },
    { decorations: (v) => v.decorations },
  ),
  EditorView.baseTheme({
    ".cm-sub-marker": {
      fontSize: "0px",
      width: "0px",
      display: "inline-block",
      overflow: "hidden",
      color: "transparent",
    },
    ".cm-relalg-sub": {
      fontSize: "0.72em",
      verticalAlign: "sub",
      lineHeight: "1",
    },
  }),
];
