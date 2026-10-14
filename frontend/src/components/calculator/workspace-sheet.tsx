"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Copy,
  Globe,
  Lock,
  MoreHorizontal,
  FolderOpen,
  Share2,
  Trash2,
  Pencil,
} from "lucide-react";
import type { DatasetDetail, DatasetSummary } from "@/lib/api";
import {
  copyDataset,
  deleteDataset,
  renameDataset,
  setDatasetVisibility,
  shareUrl,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ManagePanel,
  UploadPanel,
  BuilderPanel,
  type DataPanelTab,
} from "@/components/calculator/schema-panel";
import { GroupEditorPanel } from "@/components/calculator/group-editor";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialTab?: "workspaces" | "data";
  dataTab?: DataPanelTab;
  onDataTabChange?: (tab: DataPanelTab) => void;
  dataset: DatasetDetail | null;
  datasets: DatasetSummary[];
  onOpenWorkspace: (id: string) => void;
  onDatasetCreated: (detail: DatasetDetail) => void;
  onDatasetUpdated: (detail: DatasetDetail) => void;
  onDatasetDeleted: (id: string) => void | Promise<void>;
  onGroupsInstalled?: (groups: DatasetDetail[]) => void;
  onRefreshList?: () => void | Promise<void>;
};

function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function sortByCreated(items: DatasetSummary[]): DatasetSummary[] {
  return items.slice().sort((a, b) => {
    const ta = a.createdAt ? Date.parse(a.createdAt) : 0;
    const tb = b.createdAt ? Date.parse(b.createdAt) : 0;
    if (tb !== ta) return tb - ta;
    return a.name.localeCompare(b.name);
  });
}

export function WorkspaceSheet({
  open,
  onOpenChange,
  initialTab = "workspaces",
  dataTab = "manage",
  onDataTabChange,
  dataset,
  datasets,
  onOpenWorkspace,
  onDatasetCreated,
  onDatasetUpdated,
  onDatasetDeleted,
  onGroupsInstalled,
  onRefreshList,
}: Props) {
  const [mainTab, setMainTab] = useState<"workspaces" | "data">(initialTab);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setMainTab(initialTab);
      setError(null);
    }
  }, [open, initialTab]);

  const sections = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const match = (d: DatasetSummary) =>
      !q ||
      d.name.toLowerCase().includes(q) ||
      d.description.toLowerCase().includes(q);
    const builtins = sortByCreated(
      datasets.filter((d) => d.isBuiltin && match(d)),
    );
    const mine = sortByCreated(
      datasets.filter((d) => !d.isBuiltin && d.owned && match(d)),
    );
    const pub = sortByCreated(
      datasets.filter((d) => !d.isBuiltin && !d.owned && d.isPublic && match(d)),
    );
    return { builtins, mine, pub };
  }, [datasets, filter]);

  const deleteTarget = datasets.find((d) => d.id === deleteId);

  const sectionHandlers = {
    busy,
    activeId: dataset?.id,
    onOpen: (id: string) => {
      onOpenWorkspace(id);
      onOpenChange(false);
    },
    onRename: (d: DatasetSummary) => {
      setRenameId(d.id);
      setRenameDraft(d.name);
    },
    onDelete: (id: string) => setDeleteId(id),
    onTogglePublic: async (d: DatasetSummary, isPublic: boolean) => {
      setBusy(true);
      setError(null);
      try {
        const updated = await setDatasetVisibility(d.id, isPublic);
        onDatasetUpdated(updated);
        await onRefreshList?.();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Visibility update failed",
        );
      } finally {
        setBusy(false);
      }
    },
    onCopyShare: async (d: DatasetSummary) => {
      const token = d.shareToken;
      if (!token) {
        setError("Share link unavailable for this workspace.");
        return;
      }
      const url = shareUrl(token);
      try {
        await navigator.clipboard.writeText(url);
        setError(null);
      } catch {
        window.prompt("Copy share link:", url);
      }
    },
    onDuplicate: async (d: DatasetSummary, openAfter = false) => {
      setBusy(true);
      setError(null);
      try {
        const copied = await copyDataset(d.id);
        onDatasetCreated(copied);
        await onRefreshList?.();
        if (openAfter) {
          onOpenWorkspace(copied.id);
          onOpenChange(false);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Duplicate failed");
      } finally {
        setBusy(false);
      }
    },
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex h-[min(92vh,920px)] w-[min(96vw,1120px)] max-w-none translate-x-[-50%] translate-y-[-50%] flex-col gap-0 overflow-hidden p-0 sm:rounded-xl">
          <DialogHeader className="shrink-0 space-y-1 border-b px-6 py-4 text-left">
            <DialogTitle className="font-serif text-xl tracking-tight">
              Workspaces &amp; data
            </DialogTitle>
            <DialogDescription>
              Switch datasets, manage visibility, or edit relations for the open
              workspace.
            </DialogDescription>
          </DialogHeader>

          <Tabs
            value={mainTab}
            onValueChange={(v) => setMainTab(v as "workspaces" | "data")}
            className="flex min-h-0 flex-1 flex-col"
          >
            <div className="shrink-0 border-b px-6 py-3">
              <TabsList className="grid w-full max-w-md grid-cols-2">
                <TabsTrigger value="workspaces">Workspaces</TabsTrigger>
                <TabsTrigger value="data">Data</TabsTrigger>
              </TabsList>
            </div>

            {error ? (
              <Alert variant="destructive" className="mx-6 mt-3 shrink-0">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            <TabsContent
              value="workspaces"
              className="mt-0 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden"
            >
              <div className="shrink-0 px-6 py-3">
                <Input
                  placeholder="Filter workspaces…"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  aria-label="Filter workspaces"
                />
              </div>
              <ScrollArea className="min-h-0 flex-1 px-6 pb-6">
                <div className="grid gap-6 lg:grid-cols-3">
                  <DatasetSection
                    title="Built-in"
                    description="Demo datasets for practice. Duplicate to edit."
                    items={sections.builtins}
                    {...sectionHandlers}
                    onDuplicate={(d) => void sectionHandlers.onDuplicate(d, true)}
                    allowOwnerActions={false}
                  />
                  <DatasetSection
                    title="Public"
                    description="Shared by others. Open to query; duplicate to edit."
                    items={sections.pub}
                    {...sectionHandlers}
                    onDuplicate={(d) => void sectionHandlers.onDuplicate(d, true)}
                    allowOwnerActions={false}
                  />
                  <DatasetSection
                    title="Mine"
                    description="Your private and public workspaces."
                    items={sections.mine}
                    {...sectionHandlers}
                    onDuplicate={(d) => void sectionHandlers.onDuplicate(d)}
                    allowOwnerActions
                  />
                </div>
                {!sections.builtins.length &&
                !sections.mine.length &&
                !sections.pub.length ? (
                  <p className="text-sm text-muted-foreground">
                    No workspaces match this filter.
                  </p>
                ) : null}
              </ScrollArea>
            </TabsContent>

            <TabsContent
              value="data"
              className="mt-0 flex min-h-0 flex-1 flex-col overflow-hidden data-[state=inactive]:hidden"
            >
              <div className="flex shrink-0 flex-wrap gap-1 border-b px-6 py-3">
                {(
                  [
                    ["manage", "Edit"],
                    ["upload", "Upload"],
                    ["builder", "Build"],
                    ["group", "Group text"],
                  ] as const
                ).map(([id, label]) => (
                  <Button
                    key={id}
                    type="button"
                    size="sm"
                    variant={dataTab === id ? "default" : "outline"}
                    onClick={() => onDataTabChange?.(id)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
              <div
                className={`min-h-0 flex-1 px-6 py-4 ${
                  dataTab === "group"
                    ? "flex flex-col overflow-hidden"
                    : "overflow-auto"
                }`}
              >
                {dataTab === "manage" && dataset ? (
                  <ManagePanel
                    dataset={dataset}
                    busy={busy}
                    setBusy={setBusy}
                    setError={setError}
                    onUpdated={onDatasetUpdated}
                  />
                ) : null}
                {dataTab === "manage" && !dataset ? (
                  <p className="text-sm text-muted-foreground">
                    Open a workspace first, then edit its relations here.
                  </p>
                ) : null}
                {dataTab === "upload" ? (
                  <UploadPanel
                    busy={busy}
                    setBusy={setBusy}
                    setError={setError}
                    onCreated={(d) => {
                      onDatasetCreated(d);
                      setMainTab("workspaces");
                    }}
                  />
                ) : null}
                {dataTab === "builder" ? (
                  <BuilderPanel
                    busy={busy}
                    setBusy={setBusy}
                    setError={setError}
                    onCreated={(d) => {
                      onDatasetCreated(d);
                      setMainTab("workspaces");
                    }}
                  />
                ) : null}
                {dataTab === "group" ? (
                  <GroupEditorPanel
                    dataset={dataset}
                    busy={busy}
                    setBusy={setBusy}
                    setError={setError}
                    onInstalled={(groups) => {
                      onGroupsInstalled?.(groups);
                      setMainTab("workspaces");
                    }}
                  />
                ) : null}
              </div>
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(renameId)}
        onOpenChange={(o) => {
          if (!o) setRenameId(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename workspace</DialogTitle>
            <DialogDescription>
              Updates the dataset name for everyone who can see it.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="ws-rename">Name</Label>
            <Input
              id="ws-rename"
              value={renameDraft}
              onChange={(e) => setRenameDraft(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setRenameId(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={busy || !renameDraft.trim()}
              onClick={async () => {
                if (!renameId) return;
                setBusy(true);
                setError(null);
                try {
                  const updated = await renameDataset(
                    renameId,
                    renameDraft.trim(),
                  );
                  onDatasetUpdated(updated);
                  await onRefreshList?.();
                  setRenameId(null);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Rename failed");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(deleteId)}
        onOpenChange={(o) => {
          if (!o) setDeleteId(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete workspace?</DialogTitle>
            <DialogDescription>
              Permanently delete “{deleteTarget?.name}”. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setDeleteId(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={busy}
              onClick={async () => {
                if (!deleteId) return;
                setBusy(true);
                setError(null);
                try {
                  await deleteDataset(deleteId);
                  await onDatasetDeleted(deleteId);
                  setDeleteId(null);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Delete failed");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function DatasetSection({
  title,
  description,
  items,
  activeId,
  busy,
  allowOwnerActions,
  onOpen,
  onRename,
  onDelete,
  onTogglePublic,
  onCopyShare,
  onDuplicate,
}: {
  title: string;
  description: string;
  items: DatasetSummary[];
  activeId?: string | null;
  busy: boolean;
  allowOwnerActions: boolean;
  onOpen: (id: string) => void;
  onRename: (d: DatasetSummary) => void;
  onDelete: (id: string) => void;
  onTogglePublic: (d: DatasetSummary, isPublic: boolean) => void;
  onCopyShare: (d: DatasetSummary) => void;
  onDuplicate: (d: DatasetSummary) => void;
}) {
  return (
    <section className="min-w-0">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <p className="mb-3 mt-0.5 text-xs text-muted-foreground">{description}</p>
      {!items.length ? (
        <p className="rounded-md border border-dashed px-3 py-4 text-xs text-muted-foreground">
          None yet.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((d) => {
            const owned = Boolean(d.owned);
            const builtin = Boolean(d.isBuiltin);
            const isActive = d.id === activeId;
            const created = formatDate(d.createdAt);
            const updated = formatDate(d.updatedAt);
            return (
              <li
                key={d.id}
                className={`flex items-center gap-2 rounded-md border px-2 py-2 ${
                  isActive ? "border-primary/40 bg-primary/5" : "bg-background"
                }`}
              >
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => onOpen(d.id)}
                >
                  <span className="block truncate text-sm font-medium">
                    {d.name}
                  </span>
                  <span className="mt-0.5 flex flex-wrap items-center gap-1">
                    {builtin ? (
                      <Badge variant="secondary" className="text-[10px]">
                        Built-in
                      </Badge>
                    ) : null}
                    {!builtin && owned ? (
                      d.isPublic ? (
                        <Badge className="text-[10px]">Public</Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px]">
                          Private
                        </Badge>
                      )
                    ) : null}
                    {!builtin && !owned ? (
                      <Badge variant="secondary" className="text-[10px]">
                        Public
                      </Badge>
                    ) : null}
                    {created ? (
                      <span className="text-[10px] text-muted-foreground">
                        Created {created}
                      </span>
                    ) : null}
                    {!created && updated ? (
                      <span className="text-[10px] text-muted-foreground">
                        Updated {updated}
                      </span>
                    ) : null}
                  </span>
                </button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-8 w-8 p-0"
                      disabled={busy}
                      aria-label={`Actions for ${d.name}`}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => onOpen(d.id)}>
                      <FolderOpen className="h-4 w-4" />
                      Open
                    </DropdownMenuItem>
                    {allowOwnerActions && !builtin && owned ? (
                      <>
                        <DropdownMenuItem onClick={() => onRename(d)}>
                          <Pencil className="h-4 w-4" />
                          Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => onCopyShare(d)}>
                          <Share2 className="h-4 w-4" />
                          Copy share link
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => onTogglePublic(d, !d.isPublic)}
                        >
                          {d.isPublic ? (
                            <>
                              <Lock className="h-4 w-4" />
                              Make private
                            </>
                          ) : (
                            <>
                              <Globe className="h-4 w-4" />
                              Make public
                            </>
                          )}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => onDuplicate(d)}>
                          <Copy className="h-4 w-4" />
                          Duplicate
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive"
                          onClick={() => onDelete(d.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      </>
                    ) : (
                      <DropdownMenuItem onClick={() => onDuplicate(d)}>
                        <Copy className="h-4 w-4" />
                        Duplicate to mine
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
