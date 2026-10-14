"use client";

import { useRef } from "react";
import { FileUp, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type SingleProps = {
  accept?: string;
  disabled?: boolean;
  multiple?: false;
  file: File | null;
  onFileChange: (file: File | null) => void;
  label?: string;
  hint?: string;
};

type MultiProps = {
  accept?: string;
  disabled?: boolean;
  multiple: true;
  files: File[];
  onFilesChange: (files: File[]) => void;
  label?: string;
  hint?: string;
};

type Props = SingleProps | MultiProps;

export function FilePicker(props: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const {
    accept,
    disabled,
    label = "Choose a file",
    hint,
  } = props;
  const multiple = props.multiple === true;

  const applyFiles = (list: FileList | File[] | null | undefined) => {
    const arr = list ? Array.from(list) : [];
    if (multiple) {
      props.onFilesChange(arr);
    } else {
      props.onFileChange(arr[0] ?? null);
    }
  };

  const selected = multiple
    ? props.files
    : props.file
      ? [props.file]
      : [];

  return (
    <div className="space-y-2">
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        className="sr-only"
        disabled={disabled}
        onChange={(e) => applyFiles(e.target.files)}
      />
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
        }}
        onDrop={(e) => {
          e.preventDefault();
          applyFiles(e.dataTransfer.files);
        }}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-input bg-background px-4 py-6 text-center transition-colors hover:border-primary/50 hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50",
        )}
      >
        <FileUp className="h-6 w-6 text-primary" aria-hidden />
        <span className="text-sm font-medium text-foreground">{label}</span>
        {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
      </button>
      {selected.length ? (
        <ul className="space-y-1">
          {selected.map((f, i) => (
            <li
              key={`${f.name}-${i}`}
              className="flex items-center justify-between rounded-md border bg-muted/40 px-3 py-2 text-sm"
            >
              <span className="truncate font-medium">{f.name}</span>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label={`Remove ${f.name}`}
                onClick={() => {
                  if (multiple) {
                    props.onFilesChange(props.files.filter((_, j) => j !== i));
                  } else {
                    props.onFileChange(null);
                  }
                  if (inputRef.current) inputRef.current.value = "";
                }}
              >
                <X className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
