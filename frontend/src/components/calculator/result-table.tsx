"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Download } from "lucide-react";
import type { QueryResponse, QueryResultBlock } from "@/lib/api";
import { downloadCsv, resultsToCsv } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function blockTitle(block: QueryResultBlock, multi: boolean): string {
  if (block.label?.trim()) return block.label.trim();
  if (multi) return `Statement ${block.index + 1}`;
  return "Result";
}

function toCsvPayload(block: QueryResultBlock): QueryResponse {
  return {
    columns: block.columns,
    rows: block.rows,
    rowCount: block.rowCount,
    executionMs: block.executionMs,
    tree: block.tree,
    warnings: block.warnings,
  };
}

type BlockProps = {
  block: QueryResultBlock;
  multi: boolean;
  expanded: boolean;
  onToggle: () => void;
};

function ResultBlockView({ block, multi, expanded, onToggle }: BlockProps) {
  const title = blockTitle(block, multi);
  const meta = (
    <>
      {block.rowCount} row{block.rowCount === 1 ? "" : "s"}
      {block.rows.length < block.rowCount
        ? ` (showing ${block.rows.length})`
        : ""}
      <span className="ml-2">{block.executionMs.toFixed(2)} ms</span>
    </>
  );

  if (!multi) {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <div className="flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2 text-xs text-muted-foreground">
          <span>{meta}</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 gap-1.5"
            onClick={() =>
              downloadCsv("playground-results.csv", resultsToCsv(toCsvPayload(block)))
            }
          >
            <Download className="h-3.5 w-3.5" aria-hidden />
            CSV
          </Button>
        </div>
        {block.warnings.length > 0 ? (
          <ul className="shrink-0 space-y-0.5 border-b bg-amber-500/10 px-3 py-2 text-xs text-amber-950">
            {block.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        ) : null}
        <div className="min-h-0 flex-1 overflow-auto">
          <DataTable block={block} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex shrink-0 flex-col border-b border-border/80 last:border-b-0">
      <div className="flex shrink-0 items-center gap-1 border-b bg-muted/20 px-1 py-0.5">
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-7 w-7 shrink-0"
          aria-label={expanded ? `Collapse ${title}` : `Expand ${title}`}
          aria-expanded={expanded}
          onClick={onToggle}
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4" aria-hidden />
          ) : (
            <ChevronRight className="h-4 w-4" aria-hidden />
          )}
        </Button>
        <button
          type="button"
          className="min-w-0 flex-1 truncate px-1 py-1.5 text-left text-xs font-medium text-foreground hover:text-primary"
          onClick={onToggle}
        >
          {title}
          <span className="ml-2 font-normal text-muted-foreground">{meta}</span>
        </button>
        {expanded ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="mr-1 h-7 shrink-0 gap-1.5"
            onClick={() =>
              downloadCsv(
                `playground-results-${block.index + 1}.csv`,
                resultsToCsv(toCsvPayload(block)),
              )
            }
          >
            <Download className="h-3.5 w-3.5" aria-hidden />
            CSV
          </Button>
        ) : null}
      </div>
      {expanded ? (
        <>
          {block.warnings.length > 0 ? (
            <ul className="shrink-0 space-y-0.5 border-b bg-amber-500/10 px-3 py-2 text-xs text-amber-950">
              {block.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          ) : null}
          <div className="max-h-[min(40vh,280px)] overflow-auto">
            <DataTable block={block} />
          </div>
        </>
      ) : null}
    </div>
  );
}

function DataTable({ block }: { block: QueryResultBlock }) {
  if (block.columns.length === 0) {
    return (
      <div className="p-4 text-sm text-muted-foreground">No columns.</div>
    );
  }
  return (
    <Table>
      <TableHeader className="sticky top-0 z-10 bg-card">
        <TableRow>
          {block.columns.map((col) => (
            <TableHead key={col.name} className="whitespace-nowrap">
              {col.name}
              <span className="ml-1 font-normal text-muted-foreground">
                ({col.type})
              </span>
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {block.rows.length === 0 ? (
          <TableRow>
            <TableCell
              colSpan={block.columns.length}
              className="text-muted-foreground"
            >
              Empty result
            </TableCell>
          </TableRow>
        ) : (
          block.rows.map((row, i) => (
            <TableRow key={i}>
              {row.map((cell, j) => (
                <TableCell key={j} className="whitespace-nowrap font-mono text-xs">
                  {cell === null ? (
                    <span className="italic text-muted-foreground">null</span>
                  ) : (
                    String(cell)
                  )}
                </TableCell>
              ))}
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}

type Props = {
  result: QueryResponse | null;
  /** Index of the expanded statement, or null when all collapsed. */
  expandedIndex: number | null;
  onExpandedIndexChange: (index: number | null) => void;
};

export function ResultTable({
  result,
  expandedIndex,
  onExpandedIndexChange,
}: Props) {
  if (!result) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-sm text-muted-foreground">
        Run a query to see results.
      </div>
    );
  }

  const blocks =
    result.results && result.results.length > 0
      ? result.results
      : [
          {
            index: 0,
            label: null,
            columns: result.columns,
            rows: result.rows,
            rowCount: result.rowCount,
            executionMs: result.executionMs,
            tree: result.tree,
            warnings: result.warnings,
          } satisfies QueryResultBlock,
        ];

  const multi = blocks.length > 1;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto">
      {result.warnings.length > 0 && multi ? (
        <ul className="shrink-0 space-y-0.5 border-b bg-amber-500/10 px-3 py-2 text-xs text-amber-950">
          {result.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}
      {blocks.map((block) => {
        const expanded = !multi || block.index === expandedIndex;
        return (
          <ResultBlockView
            key={block.index}
            block={block}
            multi={multi}
            expanded={expanded}
            onToggle={() => {
              if (!multi) return;
              onExpandedIndexChange(
                block.index === expandedIndex ? null : block.index,
              );
            }}
          />
        );
      })}
    </div>
  );
}

/** Helper: default expanded index = last statement. */
export function defaultExpandedIndex(
  result: QueryResponse | null,
): number | null {
  if (!result?.results?.length) return 0;
  return result.results[result.results.length - 1]?.index ?? 0;
}

export function useResultExpandedIndex(result: QueryResponse | null) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(() =>
    defaultExpandedIndex(result),
  );
  useEffect(() => {
    setExpandedIndex(defaultExpandedIndex(result));
  }, [result]);
  return [expandedIndex, setExpandedIndex] as const;
}
