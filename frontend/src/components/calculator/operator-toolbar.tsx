"use client";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type InsertFn = (text: string, cursorOffset?: number) => void;

const SYMBOLS: {
  symbol: string;
  label: string;
  insert: string;
  cursorOffset?: number;
}[] = [
  { symbol: "π", label: "Projection — π_{columns}(relation)", insert: "π_{}()", cursorOffset: 3 },
  { symbol: "σ", label: "Selection — σ_{condition}(relation)", insert: "σ_{}()", cursorOffset: 3 },
  { symbol: "ρ", label: "Rename — ρ_{mapping}(relation)", insert: "ρ_{}()", cursorOffset: 3 },
  { symbol: "τ", label: "Order by — τ_{keys}(relation)", insert: "τ_{}()", cursorOffset: 3 },
  { symbol: "γ", label: "Group by — γ_{cols; aggs}(relation)", insert: "γ_{}()", cursorOffset: 3 },
  { symbol: "δ", label: "Duplicate elimination — δ(relation)", insert: "δ()", cursorOffset: 2 },
  { symbol: "∪", label: "Union", insert: " ∪ " },
  { symbol: "∩", label: "Intersection", insert: " ∩ " },
  { symbol: "−", label: "Set difference / except", insert: " − " },
  { symbol: "×", label: "Cross product", insert: " × " },
  { symbol: "÷", label: "Division", insert: " ÷ " },
  { symbol: "⋈", label: "Natural join", insert: " ⋈ " },
  { symbol: "⋈θ", label: "Theta join — ⋈_{condition}", insert: " ⋈_{} ", cursorOffset: 4 },
  { symbol: "⟕", label: "Left outer join", insert: " ⟕ " },
  { symbol: "⟖", label: "Right outer join", insert: " ⟖ " },
  { symbol: "⟗", label: "Full outer join", insert: " ⟗ " },
  { symbol: "⋉", label: "Left semi-join", insert: " ⋉ " },
  { symbol: "▷", label: "Anti-join", insert: " ▷ " },
  { symbol: "∧", label: "Logical and", insert: " ∧ " },
  { symbol: "∨", label: "Logical or", insert: " ∨ " },
  { symbol: "¬", label: "Logical not", insert: "¬" },
  { symbol: "≠", label: "Not equal", insert: " ≠ " },
  { symbol: "≤", label: "Less than or equal", insert: " ≤ " },
  { symbol: "≥", label: "Greater than or equal", insert: " ≥ " },
  { symbol: "→", label: "Rename arrow", insert: "→" },
];

type Props = {
  onInsert: InsertFn;
  disabled?: boolean;
};

export function OperatorToolbar({ onInsert, disabled }: Props) {
  return (
    <TooltipProvider delayDuration={200}>
      <div
        className="flex flex-wrap gap-1"
        role="toolbar"
        aria-label="Relational algebra operators"
      >
        {SYMBOLS.map((item) => (
          <Tooltip key={item.symbol + item.label}>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={disabled}
                aria-label={item.label}
                className="min-w-8 font-serif text-base"
                onClick={() => onInsert(item.insert, item.cursorOffset)}
              >
                {item.symbol}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">{item.label}</TooltipContent>
          </Tooltip>
        ))}
      </div>
    </TooltipProvider>
  );
}
