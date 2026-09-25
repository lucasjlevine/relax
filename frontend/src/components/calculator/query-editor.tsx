"use client";

import CodeMirror, { type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { sql } from "@codemirror/lang-sql";
import { EditorView } from "@codemirror/view";
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

function zoneBadge(zone: CursorZone): { text: string; className: string } {
  switch (zone.kind) {
    case "subscript":
      return {
        text: `Subscript · ${zone.content}`,
        className: "bg-primary/15 text-primary ring-primary/30",
      };
    case "before-subscript":
      return {
        text: `Before subscript · ${zone.content}`,
        className: "bg-amber-500/15 text-amber-900 ring-amber-500/30",
      };
    case "after-subscript":
      return {
        text: `After subscript · ${zone.content}`,
        className: "bg-amber-500/15 text-amber-900 ring-amber-500/30",
      };
    default:
      return {
        text: "Main expression",
        className: "bg-muted text-muted-foreground ring-border",
      };
  }
}

export const QueryEditor = forwardRef<QueryEditorHandle, Props>(
  function QueryEditor({ value, language, onChange, onExecute }, ref) {
    const cmRef = useRef<ReactCodeMirrorRef>(null);
    const [zone, setZone] = useState<CursorZone>({
      kind: "main",
      label: "Main expression",
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
        ...(language === "sql"
          ? [sql()]
          : createRelalgSubscriptExtension(onZoneChange)),
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

    const badge = zoneBadge(zone);

    return (
      <div className="overflow-hidden rounded-md border bg-card">
        {language === "relalg" ? (
          <div className="flex items-center justify-between gap-2 border-b bg-muted/40 px-3 py-1.5">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
              Cursor
            </span>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${badge.className}`}
              title={zone.label}
            >
              {badge.text}
            </span>
          </div>
        ) : null}
        <CodeMirror
          ref={cmRef}
          value={value}
          height="240px"
          basicSetup={{ lineNumbers: true, foldGutter: false }}
          extensions={extensions}
          onChange={onChange}
          placeholder={
            language === "relalg"
              ? "π_{a}(σ_{a > 1}(R))   or   pi a (sigma a > 1 (R))"
              : "SELECT a FROM R WHERE a > 1"
          }
          className="text-sm"
        />
        {language === "relalg" ? (
          <p className="border-t px-3 py-1.5 text-[11px] text-muted-foreground">
            Click into a subscript to expand <code className="font-mono">_&#123;…&#125;</code>{" "}
            markers. The badge shows whether you are in the main line or a subscript.
          </p>
        ) : null}
      </div>
    );
  },
);
