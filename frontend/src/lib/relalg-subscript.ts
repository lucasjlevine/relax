import {
  Decoration,
  type DecorationSet,
  EditorView,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import { RangeSetBuilder, StateField } from "@codemirror/state";

export type CursorZone =
  | { kind: "main"; label: string }
  | { kind: "subscript"; label: string; content: string }
  | { kind: "before-subscript"; label: string; content: string }
  | { kind: "after-subscript"; label: string; content: string };

type SubscriptSpan = {
  from: number;
  innerFrom: number;
  innerTo: number;
  to: number;
  content: string;
};

function findSubscripts(text: string): SubscriptSpan[] {
  const spans: SubscriptSpan[] = [];
  const re = /_\{([^{}]*)\}/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text))) {
    const from = match.index;
    const to = from + match[0].length;
    spans.push({
      from,
      innerFrom: from + 2,
      innerTo: to - 1,
      to,
      content: match[1] ?? "",
    });
  }
  return spans;
}

function zoneForPos(pos: number, spans: SubscriptSpan[]): CursorZone {
  for (const s of spans) {
    if (pos === s.from) {
      return {
        kind: "before-subscript",
        label: "Before subscript",
        content: s.content || "…",
      };
    }
    if (pos === s.to) {
      return {
        kind: "after-subscript",
        label: "After subscript",
        content: s.content || "…",
      };
    }
    if (pos > s.from && pos < s.to) {
      if (pos <= s.innerFrom) {
        return {
          kind: "before-subscript",
          label: "At subscript open",
          content: s.content || "…",
        };
      }
      if (pos >= s.innerTo) {
        return {
          kind: "after-subscript",
          label: "At subscript close",
          content: s.content || "…",
        };
      }
      return {
        kind: "subscript",
        label: "Inside subscript",
        content: s.content || "…",
      };
    }
  }
  return { kind: "main", label: "Main expression" };
}

/** Cursor zone derived from doc + selection (no effects / no feedback loops). */
export const cursorZoneField = StateField.define<CursorZone>({
  create(state) {
    return zoneForPos(
      state.selection.main.head,
      findSubscripts(state.doc.toString()),
    );
  },
  update(value, tr) {
    if (tr.docChanged || tr.selection) {
      return zoneForPos(
        tr.state.selection.main.head,
        findSubscripts(tr.state.doc.toString()),
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
) {
  return [
    cursorZoneField,
    ViewPlugin.fromClass(
      class {
        decorations: DecorationSet;
        constructor(view: EditorView) {
          this.decorations = buildDecorations(view);
          queueMicrotask(() => onZoneChange?.(view.state.field(cursorZoneField)));
        }
        update(update: ViewUpdate) {
          if (update.docChanged || update.selectionSet || update.viewportChanged) {
            this.decorations = buildDecorations(update.view);
          }
          if (update.docChanged || update.selectionSet) {
            onZoneChange?.(update.state.field(cursorZoneField));
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

export const relalgSubscriptExtension = createRelalgSubscriptExtension();
