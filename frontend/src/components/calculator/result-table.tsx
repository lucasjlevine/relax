"use client";

import type { QueryResponse } from "@/lib/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";

type Props = {
  result: QueryResponse | null;
};

export function ResultTable({ result }: Props) {
  if (!result) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Run a query to see results.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b px-3 py-2 text-xs text-muted-foreground">
        <span>
          {result.rowCount} row{result.rowCount === 1 ? "" : "s"}
          {result.rows.length < result.rowCount
            ? ` (showing ${result.rows.length})`
            : ""}
        </span>
        <span>{result.executionMs.toFixed(2)} ms</span>
      </div>
      <ScrollArea className="flex-1">
        <Table>
          <TableHeader>
            <TableRow>
              {result.columns.map((col) => (
                <TableHead key={col.name}>
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
                  <TableCell key={j} className="font-mono text-xs">
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
      </ScrollArea>
    </div>
  );
}
