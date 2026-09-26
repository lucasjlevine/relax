"use client";

import { Download } from "lucide-react";
import type { QueryResponse } from "@/lib/api";
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

type Props = {
  result: QueryResponse | null;
};

export function ResultTable({ result }: Props) {
  if (!result) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-sm text-muted-foreground">
        Run a query to see results.
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2 text-xs text-muted-foreground">
        <span>
          {result.rowCount} row{result.rowCount === 1 ? "" : "s"}
          {result.rows.length < result.rowCount
            ? ` (showing ${result.rows.length})`
            : ""}
          <span className="ml-2">{result.executionMs.toFixed(2)} ms</span>
        </span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 gap-1.5"
          onClick={() => {
            downloadCsv("relax-results.csv", resultsToCsv(result));
          }}
        >
          <Download className="h-3.5 w-3.5" aria-hidden />
          CSV
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-card">
            <TableRow>
              {result.columns.map((col) => (
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
            {result.rows.map((row, i) => (
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
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
