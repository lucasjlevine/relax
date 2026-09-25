"use client";

import { Button } from "@/components/ui/button";

const SYMBOLS: { symbol: string; label: string; insert: string }[] = [
  { symbol: "π", label: "Projection", insert: "π " },
  { symbol: "σ", label: "Selection", insert: "σ " },
  { symbol: "ρ", label: "Rename", insert: "ρ " },
  { symbol: "∪", label: "Union", insert: " ∪ " },
  { symbol: "∩", label: "Intersect", insert: " ∩ " },
  { symbol: "−", label: "Difference", insert: " − " },
  { symbol: "×", label: "Cross product", insert: " × " },
  { symbol: "⋈", label: "Join", insert: " ⋈ " },
  { symbol: "∧", label: "And", insert: " ∧ " },
  { symbol: "∨", label: "Or", insert: " ∨ " },
  { symbol: "¬", label: "Not", insert: "¬" },
  { symbol: "≠", label: "Not equal", insert: " != " },
  { symbol: "≤", label: "Less or equal", insert: " <= " },
  { symbol: "≥", label: "Greater or equal", insert: " >= " },
  { symbol: "→", label: "Arrow", insert: "→" },
];

type Props = {
  onInsert: (text: string) => void;
  disabled?: boolean;
};

export function OperatorToolbar({ onInsert, disabled }: Props) {
  return (
    <div className="flex flex-wrap gap-1" role="toolbar" aria-label="Relational algebra operators">
      {SYMBOLS.map((item) => (
        <Button
          key={item.symbol}
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          aria-label={item.label}
          title={item.label}
          className="min-w-8 font-serif text-base"
          onClick={() => onInsert(item.insert)}
        >
          {item.symbol}
        </Button>
      ))}
    </div>
  );
}
