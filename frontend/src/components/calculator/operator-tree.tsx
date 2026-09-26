"use client";

import type { OperatorTreeNode } from "@/lib/api";

type Props = {
  tree: OperatorTreeNode | null;
};

function TreeNode({ node, depth = 0 }: { node: OperatorTreeNode; depth?: number }) {
  return (
    <li className="min-w-0">
      <div
        className="flex min-w-0 items-start gap-1.5 rounded-md px-1.5 py-1 font-mono text-xs hover:bg-muted/60"
        style={{ paddingLeft: `${depth * 0.65 + 0.25}rem` }}
      >
        <span className="mt-0.5 inline-flex h-4 shrink-0 items-center justify-center rounded bg-primary/10 px-1 text-[9px] uppercase leading-none text-primary">
          {node.operator.slice(0, 3)}
        </span>
        <span className="min-w-0 break-words leading-snug">{node.label}</span>
      </div>
      {node.children.length > 0 ? (
        <ul className="min-w-0">
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
      <div className="flex h-full items-center justify-center p-3 text-center text-xs text-muted-foreground">
        Operator tree appears after execution.
      </div>
    );
  }

  return (
    <div className="h-full min-h-0 overflow-auto p-2">
      <ul aria-label="Operator tree" className="min-w-0">
        <TreeNode node={tree} />
      </ul>
    </div>
  );
}
