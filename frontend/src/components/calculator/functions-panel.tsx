"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

type FnRow = { sig: string; note: string };

const SECTIONS: { title: string; rows: FnRow[]; example?: string }[] = [
  {
    title: "Row & random",
    rows: [
      { sig: "rownum()", note: "0-based row index (left side in joins)" },
      { sig: "rand()", note: "Random number in [0, 1]" },
    ],
    example: "σ_{rownum() < 3}(τ_{salary desc}(Employee))",
  },
  {
    title: "Strings",
    rows: [
      { sig: "length(s)", note: "Character length" },
      { sig: "upper(s) / lower(s)", note: "Case conversion" },
      { sig: "concat(s1, s2, …)", note: "Concatenate" },
    ],
    example: "π_{upper(name)→n}(Employee)",
  },
  {
    title: "Dates",
    rows: [
      { sig: "date(s)", note: "Parse YYYY-MM-DD" },
      { sig: "adddate(d, n) / subdate(d, n)", note: "Add / subtract days" },
      { sig: "year(d) / month(d) / day(d)", note: "Parts (month is 1–12)" },
      { sig: "now()", note: "Current timestamp" },
    ],
  },
  {
    title: "Numbers",
    rows: [
      { sig: "a + b … a % b", note: "Arithmetic" },
      { sig: "abs / round / floor / ceil", note: "Numeric helpers" },
      { sig: "mod(a, b)", note: "Modulo function form" },
    ],
  },
  {
    title: "Null & conditionals",
    rows: [
      { sig: "coalesce(a, b, …)", note: "First non-null" },
      { sig: "a xor b", note: "Exclusive or" },
      {
        sig: "CASE WHEN … THEN … ELSE … END",
        note: "SQL-style conditional",
      },
    ],
    example:
      "π_{CASE WHEN salary > 80000 THEN 'high' ELSE 'ok' END→band}(Employee)",
  },
];

type Props = {
  open: boolean;
  onClose: () => void;
  anchorRef?: React.RefObject<HTMLElement | null>;
};

export function FunctionsPanel({ open, onClose, anchorRef }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const onClick = (e: MouseEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t)) return;
      if (anchorRef?.current?.contains(t)) return;
      onClose();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open, onClose, anchorRef]);

  if (!open || typeof document === "undefined") return null;

  const rect = anchorRef?.current?.getBoundingClientRect();
  const top = rect ? rect.bottom + 6 : 56;
  const right = rect ? Math.max(8, window.innerWidth - rect.right) : 16;

  return createPortal(
    <div
      ref={ref}
      style={{ top, right }}
      className="fixed z-[100] flex max-h-[min(70vh,32rem)] w-[min(26rem,92vw)] flex-col overflow-hidden rounded-md border bg-card shadow-xl"
      role="dialog"
      aria-label="Helper functions"
    >
      <div className="flex items-center justify-between border-b px-3 py-2">
        <div>
          <h2 className="text-sm font-medium text-foreground">Functions</h2>
          <p className="text-xs text-muted-foreground">
            Use in π / σ / join expressions — SQL-style names
          </p>
        </div>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          aria-label="Close functions"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2 text-sm">
        {SECTIONS.map((sec) => (
          <section key={sec.title} className="mb-4 last:mb-1">
            <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {sec.title}
            </h3>
            <ul className="space-y-1">
              {sec.rows.map((row) => (
                <li
                  key={row.sig}
                  className="grid grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] gap-2 text-xs"
                >
                  <code className="truncate font-mono text-foreground">
                    {row.sig}
                  </code>
                  <span className="text-muted-foreground">{row.note}</span>
                </li>
              ))}
            </ul>
            {sec.example ? (
              <pre className="mt-2 overflow-x-auto rounded bg-muted/60 px-2 py-1.5 font-mono text-[11px] leading-snug text-foreground/90">
                {sec.example}
              </pre>
            ) : null}
          </section>
        ))}
        <p className="border-t pt-2 text-[11px] text-muted-foreground">
          Aggregates for γ: count, sum, avg, min, max. Autocomplete suggests
          relations, attributes, and these helpers.
        </p>
      </div>
    </div>,
    document.body,
  );
}
