"use client";

import { Button } from "@/components/ui/button";

type InsertFn = (text: string, cursorOffset?: number) => void;

const SYMBOLS: {
  symbol: string;
  label: string;
  insert: string;
  cursorOffset?: number;
}[] = [
  { symbol: "π", label: "Projection (subscript)", insert: "π_{}()", cursorOffset: 3 },
  { symbol: "σ", label: "Selection (subscript)", insert: "σ_{}()", cursorOffset: 3 },
  { symbol: "ρ", label: "Rename (subscript)", insert: "ρ_{}()", cursorOffset: 3 },
  { symbol: "τ", label: "Order by (subscript)", insert: "τ_{}()", cursorOffset: 3 },
  { symbol: "γ", label: "Group by (subscript)", insert: "γ_{}()", cursorOffset: 3 },
  { symbol: "δ", label: "Distinct", insert: "δ()" , cursorOffset: 2 },
  { symbol: "∪", label: "Union", insert: " ∪ " },
  { symbol: "∩", label: "Intersect", insert: " ∩ " },
  { symbol: "−", label: "Difference", insert: " − " },
  { symbol: "×", label: "Cross product", insert: " × " },
  { symbol: "÷", label: "Division", insert: " ÷ " },
  { symbol: "⋈", label: "Join", insert: " ⋈ " },
  { symbol: "⋈θ", label: "Theta join subscript", insert: " ⋈_{} ", cursorOffset: 4 },
  { symbol: "⟕", label: "Left outer join", insert: " ⟕ " },
  { symbol: "⟖", label: "Right outer join", insert: " ⟖ " },
  { symbol: "⟗", label: "Full outer join", insert: " ⟗ " },
  { symbol: "⋉", label: "Left semi join", insert: " ⋉ " },
  { symbol: "▷", label: "Anti join", insert: " ▷ " },
  { symbol: "∧", label: "And", insert: " ∧ " },
  { symbol: "∨", label: "Or", insert: " ∨ " },
  { symbol: "¬", label: "Not", insert: "¬" },
  { symbol: "≠", label: "Not equal", insert: " ≠ " },
  { symbol: "≤", label: "Less or equal", insert: " ≤ " },
  { symbol: "≥", label: "Greater or equal", insert: " ≥ " },
  { symbol: "→", label: "Arrow", insert: "→" },
];

type Props = {
  onInsert: InsertFn;
  disabled?: boolean;
};

export function OperatorToolbar({ onInsert, disabled }: Props) {
  return (
    <div className="flex flex-wrap gap-1" role="toolbar" aria-label="Relational algebra operators">
      {SYMBOLS.map((item) => (
        <Button
          key={item.symbol + item.label}
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          aria-label={item.label}
          title={item.label}
          className="min-w-8 font-serif text-base"
          onClick={() => onInsert(item.insert, item.cursorOffset)}
        >
          {item.symbol}
        </Button>
      ))}
    </div>
  );
}
