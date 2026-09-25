"use client";

import CodeMirror, { type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { sql } from "@codemirror/lang-sql";
import { EditorView } from "@codemirror/view";
import { forwardRef, useImperativeHandle, useRef } from "react";
import type { QueryLanguage } from "@/lib/api";

export type QueryEditorHandle = {
  insertAtCursor: (text: string, cursorOffset?: number) => void;
  focus: () => void;
};

type Props = {
  value: string;
  language: QueryLanguage;
  onChange: (value: string) => void;
  onExecute: () => void;
};

export const QueryEditor = forwardRef<QueryEditorHandle, Props>(
  function QueryEditor({ value, language, onChange, onExecute }, ref) {
    const cmRef = useRef<ReactCodeMirrorRef>(null);

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

    return (
      <div className="overflow-hidden rounded-md border bg-card">
        <CodeMirror
          ref={cmRef}
          value={value}
          height="240px"
          basicSetup={{ lineNumbers: true, foldGutter: false }}
          extensions={[
            ...(language === "sql" ? [sql()] : []),
            EditorView.domEventHandlers({
              keydown(event) {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                  event.preventDefault();
                  onExecute();
                }
              },
            }),
          ]}
          onChange={onChange}
          placeholder={
            language === "relalg"
              ? "π_{a}(σ_{a > 1}(R))   or   pi a (sigma a > 1 (R))"
              : "SELECT a FROM R WHERE a > 1"
          }
          className="text-sm"
        />
      </div>
    );
  },
);
