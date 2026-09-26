"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { QueryResponse } from "@/lib/api";
import {
  ResultTable,
  useResultExpandedIndex,
} from "@/components/calculator/result-table";
import { OperatorTreeView } from "@/components/calculator/operator-tree";
import { Button } from "@/components/ui/button";

const TREE_MIN = 160;
const TREE_MAX = 520;
const TREE_DEFAULT = 240;
const RESULTS_HEIGHT_MIN = 140;
const RESULTS_HEIGHT_DEFAULT = 280;
const TREE_WIDTH_KEY = "relax.treeWidth";
const RESULTS_HEIGHT_KEY = "relax.resultsHeight";
const RESULTS_COLLAPSED_KEY = "relax.resultsCollapsed";
const TREE_COLLAPSED_KEY = "relax.treeCollapsed";

type Props = {
  result: QueryResponse | null;
};

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}

function PaneHeader({
  title,
  collapsed,
  onToggle,
}: {
  title: string;
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center gap-0.5 border-b bg-muted/30 px-1 py-0.5">
      <Button
        type="button"
        size="icon"
        variant="ghost"
        className="h-7 w-7 shrink-0"
        aria-label={collapsed ? `Expand ${title}` : `Collapse ${title}`}
        aria-expanded={!collapsed}
        onClick={onToggle}
      >
        {collapsed ? (
          <ChevronRight className="h-4 w-4" aria-hidden />
        ) : (
          <ChevronDown className="h-4 w-4" aria-hidden />
        )}
      </Button>
      <button
        type="button"
        className="min-w-0 flex-1 truncate px-1 py-1 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground"
        onClick={onToggle}
      >
        {title}
      </button>
    </div>
  );
}

export function ResultsWorkspace({ result }: Props) {
  const [treeWidth, setTreeWidth] = useState(TREE_DEFAULT);
  const [resultsHeight, setResultsHeight] = useState(RESULTS_HEIGHT_DEFAULT);
  const [resultsCollapsed, setResultsCollapsed] = useState(false);
  const [treeCollapsed, setTreeCollapsed] = useState(false);
  const [isMd, setIsMd] = useState(false);
  const [expandedIndex, setExpandedIndex] = useResultExpandedIndex(result);
  const stripRef = useRef<HTMLDivElement>(null);

  const multi =
    !!result?.results && result.results.length > 1;
  const resultsTitle = multi
    ? `Results (${result!.results!.length})`
    : "Results";

  const activeBlock =
    expandedIndex !== null
      ? (result?.results?.find((b) => b.index === expandedIndex) ?? null)
      : null;
  const activeTree = activeBlock?.tree ?? result?.tree ?? null;
  const activeTreeLabel =
    multi && activeBlock
      ? activeBlock.label?.trim() || `Statement ${activeBlock.index + 1}`
      : null;

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const sync = () => setIsMd(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    try {
      const tw = localStorage.getItem(TREE_WIDTH_KEY);
      const rh = localStorage.getItem(RESULTS_HEIGHT_KEY);
      if (tw) setTreeWidth(clamp(Number(tw), TREE_MIN, TREE_MAX));
      if (rh) setResultsHeight(Number(rh));
      if (localStorage.getItem(RESULTS_COLLAPSED_KEY) === "1") {
        setResultsCollapsed(true);
      }
      if (localStorage.getItem(TREE_COLLAPSED_KEY) === "1") {
        setTreeCollapsed(true);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(TREE_WIDTH_KEY, String(treeWidth));
      localStorage.setItem(RESULTS_HEIGHT_KEY, String(resultsHeight));
      localStorage.setItem(RESULTS_COLLAPSED_KEY, resultsCollapsed ? "1" : "0");
      localStorage.setItem(TREE_COLLAPSED_KEY, treeCollapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [treeWidth, resultsHeight, resultsCollapsed, treeCollapsed]);

  const onTreeResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = treeWidth;
      const onMove = (ev: MouseEvent) => {
        setTreeWidth(clamp(startWidth + (startX - ev.clientX), TREE_MIN, TREE_MAX));
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [treeWidth],
  );

  const onHeightResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startY = e.clientY;
      const startHeight = resultsHeight;
      const onMove = (ev: MouseEvent) => {
        const parent = stripRef.current?.parentElement;
        const maxH = parent
          ? Math.floor(parent.clientHeight * 0.75)
          : 640;
        setResultsHeight(
          clamp(startHeight + (startY - ev.clientY), RESULTS_HEIGHT_MIN, maxH),
        );
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [resultsHeight],
  );

  const bothCollapsed = resultsCollapsed && treeCollapsed;
  const showTreeFixed = isMd && !treeCollapsed && !resultsCollapsed;

  return (
    <>
      <button
        type="button"
        aria-label="Resize results height"
        className="h-1.5 w-full shrink-0 cursor-row-resize border-t bg-transparent hover:bg-primary/20 active:bg-primary/30"
        onMouseDown={onHeightResizeStart}
      />
      <div
        ref={stripRef}
        className="flex min-h-0 shrink-0 flex-col overflow-hidden md:flex-row"
        style={
          bothCollapsed
            ? { height: "auto" }
            : { height: resultsHeight, minHeight: RESULTS_HEIGHT_MIN }
        }
      >
        <section
          className={`flex min-h-0 min-w-0 flex-col border-b md:border-b-0 md:border-r ${
            resultsCollapsed ? "md:w-[8.5rem] md:shrink-0" : "flex-1"
          }`}
        >
          <PaneHeader
            title={resultsTitle}
            collapsed={resultsCollapsed}
            onToggle={() => setResultsCollapsed((c) => !c)}
          />
          {!resultsCollapsed ? (
            <div className="min-h-0 flex-1 overflow-hidden">
              <ResultTable
                result={result}
                expandedIndex={expandedIndex}
                onExpandedIndexChange={setExpandedIndex}
              />
            </div>
          ) : null}
        </section>

        {showTreeFixed ? (
          <button
            type="button"
            aria-label="Resize operator tree width"
            className="hidden w-1.5 shrink-0 cursor-col-resize bg-transparent hover:bg-primary/20 active:bg-primary/30 md:block"
            onMouseDown={onTreeResizeStart}
          />
        ) : null}

        <section
          className={`flex min-h-0 flex-col overflow-hidden ${
            treeCollapsed
              ? "md:w-[9.5rem] md:shrink-0"
              : resultsCollapsed
                ? "min-w-0 flex-1"
                : "min-w-0 shrink-0 md:border-l-0"
          }`}
          style={showTreeFixed ? { width: treeWidth } : undefined}
        >
          <PaneHeader
            title={
              activeTreeLabel ? `Tree · ${activeTreeLabel}` : "Operator tree"
            }
            collapsed={treeCollapsed}
            onToggle={() => setTreeCollapsed((c) => !c)}
          />
          {!treeCollapsed ? (
            <div className="min-h-0 flex-1 overflow-auto p-2">
              <OperatorTreeView tree={activeTree} />
            </div>
          ) : null}
        </section>
      </div>
    </>
  );
}
