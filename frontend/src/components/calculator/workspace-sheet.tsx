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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
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
    if (open) setMainTab(initialTab);
  }, [open, initialTab]);

  const sections = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const match = (d: DatasetSummary) =>
      !q ||
      d.name.toLowerCase().includes(q) ||
      d.description.toLowerCase().includes(q);
    const builtins = datasets.filter((d) => d.isBuiltin && match(d));
    const mine = datasets.filter(
      (d) => !d.isBuiltin && d.owned && match(d),
    );
    const pub = datasets.filter(
      (d) => !d.isBuiltin && !d.owned && d.isPublic && match(d),
    );
    return { builtins, mine, pub };
  }, [datasets, filter]);

  const deleteTarget = datasets.find((d) => d.id === deleteId);

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent
          side="left"
          className="flex w-full flex-col gap-0 p-0 sm:max-w-lg"
        >
          <SheetHeader className="shrink-0 border-b px-4 py-4 text-left">
            <SheetTitle>Workspaces &amp; data</SheetTitle>
            <SheetDescription>
              Open a dataset workspace, change visibility, or manage relations.
            </SheetDescription>
          </SheetHeader>

          <Tabs
            value={mainTab}
            onValueChange={(v) => setMainTab(v as "workspaces" | "data")}
            className="flex min-h-0 flex-1 flex-col"
          >
            <div className="shrink-0 border-b px-4 py-2">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="workspaces">Workspaces</TabsTrigger>
                <TabsTrigger value="data">Data</TabsTrigger>
              </TabsList>
            </div>

            {error ? (
              <Alert variant="destructive" className="mx-4 mt-3 shrink-0">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            <TabsContent
              value="workspaces"
              className="mt-0 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden"
            >
              <div className="shrink-0 px-4 py-3">
                <Input
                  placeholder="Filter workspaces…"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  aria-label="Filter workspaces"
                />
              </div>
              <ScrollArea className="min-h-0 flex-1 px-4 pb-4">
                <DatasetSection
                  title="Built-in"
                  items={sections.builtins}
                  activeId={dataset?.id}
                  busy={busy}
                  onOpen={(id) => {
                    onOpenWorkspace(id);
                    onOpenChange(false);
                  }}
                  onRename={(d) => {
                    setRenameId(d.id);
                    setRenameDraft(d.name);
                  }}
                  onDelete={(id) => setDeleteId(id)}
                  onTogglePublic={async (d, isPublic) => {
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
                  }}
                  onCopyShare={async (d) => {
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
                  }}
                  onDuplicate={async (d) => {
                    setBusy(true);
                    setError(null);
                    try {
                      const copied = await copyDataset(d.id);
                      onDatasetCreated(copied);
                      await onRefreshList?.();
                      onOpenWorkspace(copied.id);
                      onOpenChange(false);
                    } catch (err) {
                      setError(
                        err instanceof Error ? err.message : "Duplicate failed",
                      );
                    } finally {
                      setBusy(false);
                    }
                  }}
                />
                <DatasetSection
                  title="Mine"
                  items={sections.mine}
                  activeId={dataset?.id}
                  busy={busy}
                  onOpen={(id) => {
                    onOpenWorkspace(id);
                    onOpenChange(false);
                  }}
                  onRename={(d) => {
                    setRenameId(d.id);
                    setRenameDraft(d.name);
                  }}
                  onDelete={(id) => setDeleteId(id)}
                  onTogglePublic={async (d, isPublic) => {
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
                  }}
                  onCopyShare={async (d) => {
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
                  }}
                  onDuplicate={async (d) => {
                    setBusy(true);
                    setError(null);
                    try {
                      const copied = await copyDataset(d.id);
                      onDatasetCreated(copied);
                      await onRefreshList?.();
                    } catch (err) {
                      setError(
                        err instanceof Error ? err.message : "Duplicate failed",
                      );
                    } finally {
                      setBusy(false);
                    }
                  }}
                />
                <DatasetSection
                  title="Public"
                  items={sections.pub}
                  activeId={dataset?.id}
                  busy={busy}
                  onOpen={(id) => {
                    onOpenWorkspace(id);
                    onOpenChange(false);
                  }}
                  onRename={() => undefined}
                  onDelete={() => undefined}
                  onTogglePublic={() => undefined}
                  onCopyShare={() => undefined}
                  onDuplicate={async (d) => {
                    setBusy(true);
                    setError(null);
                    try {
                      const copied = await copyDataset(d.id);
                      onDatasetCreated(copied);
                      await onRefreshList?.();
                      onOpenWorkspace(copied.id);
                      onOpenChange(false);
                    } catch (err) {
                      setError(
                        err instanceof Error ? err.message : "Duplicate failed",
                      );
                    } finally {
                      setBusy(false);
                    }
                  }}
                />
              </ScrollArea>
            </TabsContent>

            <TabsContent
              value="data"
              className="mt-0 flex min-h-0 flex-1 flex-col overflow-hidden data-[state=inactive]:hidden"
            >
              <div className="flex shrink-0 flex-wrap gap-1 border-b px-4 py-2">
                {(
                  [
                    ["manage", "Manage"],
                    ["upload", "Upload"],
                    ["builder", "Build"],
                    ["group", "Group"],
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
                className={`min-h-0 flex-1 p-4 ${
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
                    onDeleted={onDatasetDeleted}
                  />
                ) : null}
                {dataTab === "manage" && !dataset ? (
                  <p className="text-sm text-muted-foreground">
                    Open a workspace to manage its relations.
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
        </SheetContent>
      </Sheet>

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
  items,
  activeId,
  busy,
  onOpen,
  onRename,
  onDelete,
  onTogglePublic,
  onCopyShare,
  onDuplicate,
}: {
  title: string;
  items: DatasetSummary[];
  activeId?: string | null;
  busy: boolean;
  onOpen: (id: string) => void;
  onRename: (d: DatasetSummary) => void;
  onDelete: (id: string) => void;
  onTogglePublic: (d: DatasetSummary, isPublic: boolean) => void;
  onCopyShare: (d: DatasetSummary) => void;
  onDuplicate: (d: DatasetSummary) => void;
}) {
  if (!items.length) return null;
  return (
    <section className="mb-5">
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      <ul className="space-y-1.5">
        {items.map((d) => {
          const owned = Boolean(d.owned);
          const builtin = Boolean(d.isBuiltin);
          const isActive = d.id === activeId;
          return (
            <li
              key={d.id}
              className={`flex items-center gap-2 rounded-md border px-2 py-1.5 ${
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
                <span className="mt-0.5 flex flex-wrap gap-1">
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
                  {!builtin && owned ? (
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
                  ) : null}
                  {!builtin && !owned ? (
                    <DropdownMenuItem onClick={() => onDuplicate(d)}>
                      <Copy className="h-4 w-4" />
                      Duplicate to mine
                    </DropdownMenuItem>
                  ) : null}
                  {builtin ? (
                    <DropdownMenuItem onClick={() => onDuplicate(d)}>
                      <Copy className="h-4 w-4" />
                      Duplicate to mine
                    </DropdownMenuItem>
                  ) : null}
                </DropdownMenuContent>
              </DropdownMenu>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
