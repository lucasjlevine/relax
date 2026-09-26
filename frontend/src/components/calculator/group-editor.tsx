"use client";

import CodeMirror, { type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { keymap, EditorView } from "@codemirror/view";
import { toggleComment } from "@codemirror/commands";
import { useEffect, useMemo, useRef, useState } from "react";
import { Download, Eye, FilePlus2, Play, Upload } from "lucide-react";
import {
  exportDatasetText,
  installGroupText,
  previewGroupText,
  type DatasetDetail,
} from "@/lib/api";
import { editorHighlight } from "@/lib/editor-theme";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const STORAGE_KEY = "relax.groupEditorText";

export const DEFAULT_GROUP_TEXT = `group: sample group
description: this is the description

exampleSql - {
  Select * from A where a = 1
}

exampleRelAlg - {
  σ_{a = 1}(A)
}

A = {
a:number, b:number
1, 2
3, 4
}

B = {
a:number, c:string, d:date
1, 'test', 1970-01-01
3, 'test2', null
}
`;

const INSERT_RELATION = `
R = {
a:number, b:string
1, hello
}
`;

type Props = {
  dataset: DatasetDetail | null;
  busy: boolean;
  setBusy: (v: boolean) => void;
  setError: (v: string | null) => void;
  onInstalled: (groups: DatasetDetail[]) => void;
};

export function GroupEditorPanel({
  dataset,
  busy,
  setBusy,
  setError,
  onInstalled,
}: Props) {
  const cmRef = useRef<ReactCodeMirrorRef>(null);
  const [text, setText] = useState(DEFAULT_GROUP_TEXT);
  const [preview, setPreview] = useState<DatasetDetail[] | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setText(saved);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, text);
    } catch {
      /* ignore */
    }
  }, [text]);

  const extensions = useMemo(
    () => [
      ...editorHighlight,
      keymap.of([{ key: "Mod-/", run: toggleComment }]),
      EditorView.lineWrapping,
    ],
    [],
  );

  const insertAtCursor = (snippet: string) => {
    const view = cmRef.current?.view;
    if (!view) {
      setText((t) => t.trimEnd() + "\n" + snippet.trimStart());
      return;
    }
    const { from, to } = view.state.selection.main;
    const insert = snippet.startsWith("\n") ? snippet : `\n${snippet}`;
    view.dispatch({
      changes: { from, to, insert },
      selection: { anchor: from + insert.length },
    });
    view.focus();
  };

  const runPreview = async () => {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const groups = await previewGroupText(text);
      setPreview(groups);
      setStatus(
        groups.length === 1
          ? `Parsed 1 group · ${groups[0].relations.length} relation(s)`
          : `Parsed ${groups.length} groups`,
      );
    } catch (err) {
      setPreview(null);
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  };

  const runInstall = async () => {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const groups = await installGroupText(text);
      setPreview(groups);
      onInstalled(groups);
      setStatus(
        groups.length === 1
          ? `Installed “${groups[0].name}”`
          : `Installed ${groups.length} groups`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Install failed");
    } finally {
      setBusy(false);
    }
  };

  const loadCurrent = async () => {
    if (!dataset) {
      setError("Select a dataset to load into the editor");
      return;
    }
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const exported = await exportDatasetText(dataset.id);
      setText(exported.text);
      setPreview(null);
      setStatus(`Loaded “${dataset.name}”`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setBusy(false);
    }
  };

  const download = () => {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${dataset?.id ?? "local_groups"}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 text-sm">
      <div>
        <p className="text-muted-foreground">
          RelaX-compatible <span className="font-mono text-xs">local_groups</span>{" "}
          editor. Preview parses without installing; Use adds groups to your session.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => void runPreview()}
        >
          <Eye className="h-3.5 w-3.5" />
          Preview
        </Button>
        <Button type="button" size="sm" disabled={busy} onClick={() => void runInstall()}>
          <Play className="h-3.5 w-3.5" />
          Use
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy || !dataset}
          onClick={() => void loadCurrent()}
        >
          <Upload className="h-3.5 w-3.5" />
          Load current
        </Button>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={download}>
          <Download className="h-3.5 w-3.5" />
          Download
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => insertAtCursor(INSERT_RELATION)}
        >
          <FilePlus2 className="h-3.5 w-3.5" />
          Insert relation
        </Button>
      </div>

      {status ? <p className="text-xs text-primary">{status}</p> : null}

      <div className="min-h-[14rem] flex-1 overflow-hidden rounded-md border bg-background">
        <CodeMirror
          ref={cmRef}
          value={text}
          height="100%"
          minHeight="14rem"
          basicSetup={{
            lineNumbers: true,
            foldGutter: true,
            highlightActiveLine: true,
          }}
          extensions={extensions}
          onChange={setText}
          className="h-full text-xs [&_.cm-editor]:h-full [&_.cm-scroller]:min-h-[14rem]"
        />
      </div>

      {preview && preview.length > 0 ? (
        <div className="space-y-2">
          <Label className="text-xs uppercase tracking-wide text-muted-foreground">
            Preview
          </Label>
          <ul className="space-y-2">
            {preview.map((g) => (
              <li key={g.id} className="rounded-md border bg-background p-2">
                <div className="font-medium text-foreground">{g.name}</div>
                {g.description ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">{g.description}</p>
                ) : null}
                <ul className="mt-1 space-y-0.5">
                  {g.relations.map((r) => (
                    <li key={r.name} className="font-mono text-xs text-muted-foreground">
                      {r.name}
                      <span className="text-foreground/40">
                        {" "}
                        · {r.columns.map((c) => c.name).join(", ")} · {r.rowCount} rows
                      </span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
