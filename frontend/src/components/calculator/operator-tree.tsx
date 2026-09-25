"use client";

import type { OperatorTreeNode } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";

type Props = {
  tree: OperatorTreeNode | null;
};

function TreeNode({ node, depth = 0 }: { node: OperatorTreeNode; depth?: number }) {
  return (
    <li>
      <div
        className="flex items-center gap-2 rounded-md px-2 py-1 font-mono text-sm hover:bg-muted/60"
        style={{ paddingLeft: `${depth * 1 + 0.5}rem` }}
      >
        <span className="inline-flex h-5 min-w-5 items-center justify-center rounded bg-primary/10 px-1 text-[10px] uppercase text-primary">
          {node.operator.slice(0, 3)}
        </span>
        <span>{node.label}</span>
      </div>
      {node.children.length > 0 ? (
        <ul>
          {node.children.map((child) => (
            <TreeNode key={child.id} node={child} depth={depth + 1} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function OperatorTreeView({ tree }: Props) {
  if (!tree) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Operator tree appears after execution.
      </div>
    );
  }

  return (
    <ScrollArea className="h-full p-2">
      <ul aria-label="Operator tree">
        <TreeNode node={tree} />
      </ul>
    </ScrollArea>
  );
}
