"use client";

import CodeMirror, { type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { sql } from "@codemirror/lang-sql";
import { keymap, EditorView } from "@codemirror/view";
import { toggleComment } from "@codemirror/commands";
import {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import type { QueryLanguage } from "@/lib/api";
import {
  createRelalgSubscriptExtension,
  type CursorZone,
} from "@/lib/relalg-subscript";
import {
  createSchemaCompletions,
  type SchemaHint,
} from "@/lib/query-completions";
import { relalg } from "@/lib/relalg-language";
import { editorHighlight } from "@/lib/editor-theme";

export type QueryEditorHandle = {
  insertAtCursor: (text: string, cursorOffset?: number) => void;
  focus: () => void;
};

type Props = {
  value: string;
  language: QueryLanguage;
  onChange: (value: string) => void;
  onExecute: () => void;
  schema?: SchemaHint | null;
};

function zoneClass(kind: CursorZone["kind"]): string {
  switch (kind) {
    case "subscript":
      return "bg-primary/15 text-primary ring-primary/30";
    case "before-subscript":
    case "after-subscript":
      return "bg-amber-500/15 text-amber-900 ring-amber-500/30";
    default:
      return "bg-muted text-muted-foreground ring-border";
  }
}

export const QueryEditor = forwardRef<QueryEditorHandle, Props>(
  function QueryEditor({ value, language, onChange, onExecute, schema }, ref) {
    const cmRef = useRef<ReactCodeMirrorRef>(null);
    const schemaRef = useRef<SchemaHint | null>(schema ?? null);
    schemaRef.current = schema ?? null;
    const [zone, setZone] = useState<CursorZone>({
      kind: "main",
      badge: "1:1 · Main expression",
      label: "Outside any subscript",
      line: 1,
      column: 1,
    });

    const onZoneChange = useCallback((next: CursorZone) => {
      setZone(next);
    }, []);

    useImperativeHandle(ref, () => ({
      insertAtCursor(text: string, cursorOffset?: number) {
        const view = cmRef.current?.view;
        if (!view) {
          onChange(value + text);
          return;
        }
        const { from, to } = view.state.selection.main;
        const anchor =
          cursorOffset !== undefined ? from + cursorOffset : from + text.length;
        view.dispatch({
          changes: { from, to, insert: text },
          selection: { anchor },
        });
        view.focus();
      },
      focus() {
        cmRef.current?.view?.focus();
      },
    }));

    const extensions = useMemo(
      () => [
        ...editorHighlight,
        createSchemaCompletions(() => schemaRef.current),
        keymap.of([{ key: "Mod-/", run: toggleComment }]),
        ...(language === "sql"
          ? [sql()]
          : [
              relalg(),
              ...createRelalgSubscriptExtension(
                onZoneChange,
                () => schemaRef.current,
              ),
            ]),
        EditorView.domEventHandlers({
          keydown(event) {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
              event.preventDefault();
              onExecute();
            }
          },
        }),
      ],
      [language, onExecute, onZoneChange],
    );

    return (
      <div className="overflow-hidden rounded-md border bg-card">
        {language === "relalg" ? (
          <div className="flex items-center justify-between gap-2 border-b bg-muted/40 px-3 py-1.5">
            <span
              className={`max-w-full truncate rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${zoneClass(zone.kind)}`}
              title={zone.label}
            >
              {zone.badge}
            </span>
          </div>
        ) : null}
        <CodeMirror
          ref={cmRef}
          value={value}
          height="220px"
          basicSetup={{ lineNumbers: true, foldGutter: false }}
          extensions={extensions}
          onChange={onChange}
          placeholder={
            language === "relalg"
              ? "π_{name}(σ_{dept = 'Engineering'}(Employee))"
              : "SELECT name FROM Employee WHERE dept = 'Engineering'"
          }
          className="text-sm"
        />
      </div>
    );
  },
);
