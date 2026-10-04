import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight, Columns3, FileText, FolderClosed, FolderInput, FolderMinus, FolderOpen, Loader2, MoreHorizontal, Pencil, Plus, Radar, Trash2, Trophy, Users, X,
} from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { CompetitorAvatar } from "@/components/CompetitorAvatar";
import { EmptyState, ErrorState, PageHeader } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input, Label } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Client, type Competitor } from "@/lib/api";
import { cn, formatNumber, timeAgo } from "@/lib/utils";

const MAX_COMPARE = 3;

function ClientDialog({
  open, onOpenChange, client, competitors, onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  client?: Client;
  competitors: Competitor[];
  onSaved: (c: Client) => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(client?.name ?? "");
  const [notes, setNotes] = useState(client?.notes ?? "");
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const save = useMutation({
    mutationFn: () =>
      client
        ? api.updateClient(client.id, { name: name.trim(), notes })
        : api.createClient({ name: name.trim(), notes: notes || undefined, competitor_ids: [...picked] }),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      qc.invalidateQueries({ queryKey: ["competitors"] });
      toast.success(client ? "Client updated" : `Client “${c.name}” created`);
      onSaved(c);
      onOpenChange(false);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't save"),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogTitle>{client ? "Edit client" : "New client folder"}</DialogTitle>
        <DialogDescription>Group the competitors you track for one client. Reports can then cover the whole folder.</DialogDescription>
        <form
          className="mt-2 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) save.mutate();
          }}
        >
          <div>
            <Label htmlFor="client-name">Client name</Label>
            <Input id="client-name" className="mt-1.5" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} placeholder="e.g. Northwind Fitness" autoFocus />
          </div>
          <div>
            <Label htmlFor="client-notes">Notes <span className="font-normal text-muted-foreground">(optional)</span></Label>
            <textarea
              id="client-notes"
              className="mt-1.5 min-h-16 w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
              value={notes}
              maxLength={2000}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Market, positioning, what they want to learn…"
            />
          </div>
          {!client && competitors.length > 0 && (
            <div>
              <Label>Competitors <span className="font-normal text-muted-foreground">(optional, you can move them later)</span></Label>
              <div className="mt-1.5 max-h-48 space-y-0.5 overflow-y-auto rounded-lg border border-border p-1.5">
                {competitors.map((c) => (
                  <label key={c.id} className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm hover:bg-accent">
                    <Checkbox
                      checked={picked.has(c.id)}
                      onCheckedChange={(v) => {
                        const next = new Set(picked);
                        if (v === true) next.add(c.id);
                        else next.delete(c.id);
                        setPicked(next);
                      }}
                    />
                    <CompetitorAvatar name={c.name} src={c.logo_url} className="size-5 rounded" />
                    <span className="flex-1 truncate">{c.name}</span>
                    <span className="num text-xs text-muted-foreground">{c.ad_count}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={!name.trim() || save.isPending}>
              {save.isPending && <Loader2 className="animate-spin" />} {client ? "Save" : "Create client"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RenameDialog({ competitor, onClose }: { competitor: Competitor | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState(competitor?.name ?? "");
  const save = useMutation({
    mutationFn: () => api.renameCompetitor(competitor!.id, name.trim()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["competitors"] });
      toast.success("Competitor renamed");
      onClose();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't rename"),
  });
  return (
    <Dialog open={!!competitor} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogTitle>Rename competitor</DialogTitle>
        <DialogDescription>Changes the display name in the app and in reports.</DialogDescription>
        <form className="mt-2 space-y-4" onSubmit={(e) => { e.preventDefault(); if (name.trim()) save.mutate(); }}>
          <Input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} autoFocus aria-label="Competitor name" />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={!name.trim() || save.isPending}>Save</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function FolderButton({ active, icon: Icon, label, count, onClick }: { active: boolean; icon: typeof FolderClosed; label: string; count: number; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors",
        active ? "bg-primary/12 font-medium text-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      <Icon className={cn("size-4 shrink-0", active && "text-primary")} />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span className="num text-xs opacity-70">{count}</span>
    </button>
  );
}

export default function Competitors() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const folder = params.get("client"); // null = all, "none" = unassigned, else client id
  const q = useQuery({ queryKey: ["competitors"], queryFn: api.competitors });
  const clientsQ = useQuery({ queryKey: ["clients"], queryFn: api.clients });
  const [selected, setSelected] = useState<number[]>([]);
  const [clientDialog, setClientDialog] = useState<{ client?: Client } | null>(null);
  const [renaming, setRenaming] = useState<Competitor | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Client | null>(null);

  const all = (q.data ?? []).filter((c) => c.ad_count > 0);
  const clients = clientsQ.data ?? [];
  const activeClient = folder && folder !== "none" ? clients.find((c) => String(c.id) === folder) : undefined;
  const list = all.filter((c) => (folder === null ? true : folder === "none" ? c.client_id === null : String(c.client_id) === folder));
  const setFolder = (value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null) next.delete("client");
    else next.set("client", value);
    setParams(next, { replace: true });
  };

  const assign = useMutation({
    mutationFn: ({ competitor, clientId }: { competitor: Competitor; clientId: number | null }) => api.assignClient(competitor.id, clientId),
    onSuccess: (_r, { competitor, clientId }) => {
      qc.invalidateQueries({ queryKey: ["competitors"] });
      qc.invalidateQueries({ queryKey: ["clients"] });
      const target = clients.find((c) => c.id === clientId);
      toast.success(target ? `Moved ${competitor.name} to ${target.name}` : `Removed ${competitor.name} from its client`);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't move"),
  });
  const removeClient = useMutation({
    mutationFn: (id: number) => api.deleteClient(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      qc.invalidateQueries({ queryKey: ["competitors"] });
      toast.success("Client folder deleted", { description: "Its competitors are now unassigned." });
      setConfirmDelete(null);
      setFolder(null);
    },
  });

  const toggle = (id: number, on: boolean) => {
    if (on && selected.length >= MAX_COMPARE) {
      toast.info(`Compare up to ${MAX_COMPARE} competitors at a time`);
      return;
    }
    setSelected(on ? [...selected, id] : selected.filter((x) => x !== id));
  };
  const clientName = (id: number | null) => clients.find((c) => c.id === id)?.name;

  return (
    <>
      <PageHeader
        title="Competitors"
        description="Every brand you've scanned, organised into client folders."
        actions={
          <>
            <Button variant="outline" onClick={() => setClientDialog({})}><Plus /> New client</Button>
            <Button asChild><Link to="/scan/new"><Radar /> Track a competitor</Link></Button>
          </>
        }
      />
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-44" />)}</div>
      ) : !all.length ? (
        <EmptyState icon={Users} title="No competitors yet" description="Scan a brand and it appears here with its ad count, average lifespan and last scan." action={<Button asChild><Link to="/scan/new">Start a scan</Link></Button>} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
          <nav aria-label="Client folders" className="space-y-1 lg:sticky lg:top-20 lg:self-start">
            <FolderButton active={folder === null} icon={Users} label="All competitors" count={all.length} onClick={() => setFolder(null)} />
            <div className="px-2.5 pt-3 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">Clients</div>
            {clientsQ.isLoading ? (
              <Skeleton className="h-8" />
            ) : (
              clients.map((c) => (
                <FolderButton
                  key={c.id}
                  active={folder === String(c.id)}
                  icon={folder === String(c.id) ? FolderOpen : FolderClosed}
                  label={c.name}
                  count={all.filter((x) => x.client_id === c.id).length}
                  onClick={() => setFolder(String(c.id))}
                />
              ))
            )}
            <FolderButton active={folder === "none"} icon={FolderMinus} label="Unassigned" count={all.filter((c) => c.client_id === null).length} onClick={() => setFolder("none")} />
            <button type="button" onClick={() => setClientDialog({})} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground">
              <Plus className="size-4" /> New client
            </button>
          </nav>

          <div className="min-w-0">
            {activeClient && (
              <Card className="mb-4 flex flex-wrap items-center gap-3 p-4">
                <div className="grid size-10 place-items-center rounded-lg bg-primary/12 text-primary"><FolderOpen className="size-5" /></div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">{activeClient.name}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {activeClient.notes || `${list.length} competitor${list.length !== 1 ? "s" : ""} · ${activeClient.board_count} swipe board${activeClient.board_count !== 1 ? "s" : ""}`}
                  </div>
                </div>
                <Button size="sm" disabled={!list.length} onClick={() => navigate(`/reports?client=${activeClient.id}`)}><FileText /> Client report</Button>
                {list.length >= 2 && list.length <= MAX_COMPARE && (
                  <Button size="sm" variant="outline" onClick={() => navigate(`/compare?ids=${list.map((c) => c.id).join(",")}`)}><Columns3 /> Compare all</Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => setClientDialog({ client: activeClient })} aria-label="Edit client"><Pencil /></Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(activeClient)} aria-label="Delete client"><Trash2 /></Button>
              </Card>
            )}

            {!list.length ? (
              <EmptyState
                icon={FolderInput}
                title={folder === "none" ? "Every competitor is in a client folder" : "No competitors in this folder yet"}
                description={folder === "none" ? undefined : "Open “All competitors” and use a card's ⋯ menu to move brands here."}
                action={folder !== "none" ? <Button variant="outline" onClick={() => setFolder(null)}>Show all competitors</Button> : undefined}
              />
            ) : (
              <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                {list.map((c, i) => {
                  const isSel = selected.includes(c.id);
                  return (
                    <motion.div key={c.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 12) * 0.035 }}>
                      <Card className={cn("group relative p-5 transition-all hover:-translate-y-0.5", isSel ? "border-primary ring-2 ring-primary/25" : "hover:border-primary/40")}>
                        <div className="absolute top-4 right-4 flex items-center gap-1">
                          <Checkbox
                            checked={isSel}
                            onCheckedChange={(v) => toggle(c.id, v === true)}
                            aria-label={`Select ${c.name} to compare`}
                            className={cn("transition-opacity", isSel || selected.length ? "opacity-100" : "opacity-0 group-hover:opacity-100 focus-visible:opacity-100")}
                          />
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${c.name}`}><MoreHorizontal /></Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent className="w-56">
                              <DropdownMenuLabel>Move to client</DropdownMenuLabel>
                              {clients.length ? (
                                clients.map((cl) => (
                                  <DropdownMenuItem key={cl.id} disabled={cl.id === c.client_id} onSelect={() => assign.mutate({ competitor: c, clientId: cl.id })}>
                                    <FolderClosed /> {cl.name}
                                  </DropdownMenuItem>
                                ))
                              ) : (
                                <DropdownMenuItem onSelect={() => setClientDialog({})}><Plus /> Create a client first</DropdownMenuItem>
                              )}
                              {c.client_id !== null && (
                                <DropdownMenuItem onSelect={() => assign.mutate({ competitor: c, clientId: null })}><X /> Remove from client</DropdownMenuItem>
                              )}
                              <DropdownMenuSeparator />
                              <DropdownMenuItem onSelect={() => setRenaming(c)}><Pencil /> Rename</DropdownMenuItem>
                              <DropdownMenuItem onSelect={() => navigate(`/reports?competitor=${c.id}`)}><FileText /> Generate report</DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                        <Link to={`/competitors/${c.id}`} className="block">
                          <div className="flex items-center gap-3 pr-16">
                            <CompetitorAvatar name={c.name} src={c.logo_url} className="size-11 rounded-xl" />
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-1.5 truncate font-semibold">
                                {c.name}
                                <ArrowRight className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-all group-hover:translate-x-0.5 group-hover:text-primary group-hover:opacity-100" />
                              </div>
                              <div className="truncate text-xs text-muted-foreground">
                                Last scan {timeAgo(c.last_scan_at)}
                                {folder === null && c.client_id !== null && <> · <FolderClosed className="inline size-3" /> {clientName(c.client_id)}</>}
                              </div>
                            </div>
                          </div>
                          <div className="mt-5 grid grid-cols-3 gap-2">
                            <div><div className="num text-xl font-semibold">{formatNumber(c.ad_count)}</div><div className="text-[11px] text-muted-foreground">Ads · {c.active_ads} active</div></div>
                            <div><div className="num text-xl font-semibold">{c.avg_days_running}</div><div className="text-[11px] text-muted-foreground">Avg. lifespan (days)</div></div>
                            <div><div className="num flex items-center gap-1 text-xl font-semibold text-gold"><Trophy className="size-4" />{c.winners}</div><div className="text-[11px] text-muted-foreground">Winners</div></div>
                          </div>
                        </Link>
                      </Card>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {selected.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass fixed inset-x-4 bottom-5 z-30 mx-auto flex max-w-xl items-center gap-3 rounded-xl border border-primary/40 px-4 py-2.5 shadow-xl">
          <div className="flex -space-x-2">
            {selected.map((id) => {
              const c = all.find((x) => x.id === id);
              return c ? <CompetitorAvatar key={id} name={c.name} src={c.logo_url} className="size-7 rounded-lg ring-2 ring-background" /> : null;
            })}
          </div>
          <span className="text-sm font-medium">{selected.length} of {MAX_COMPARE} selected</span>
          <div className="ml-auto flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => setSelected([])}>Clear</Button>
            <Button size="sm" onClick={() => navigate(`/compare?ids=${selected.join(",")}`)}><Columns3 /> {selected.length === 1 ? "Open in Compare" : "Compare"}</Button>
          </div>
        </motion.div>
      )}

      {clientDialog && (
        <ClientDialog
          open
          onOpenChange={(o) => !o && setClientDialog(null)}
          client={clientDialog.client}
          competitors={all}
          onSaved={(c) => setFolder(String(c.id))}
        />
      )}
      {renaming && <RenameDialog competitor={renaming} onClose={() => setRenaming(null)} />}
      <Dialog open={!!confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <DialogContent className="max-w-sm">
          <DialogTitle>Delete “{confirmDelete?.name}”?</DialogTitle>
          <DialogDescription>Only the folder is deleted. Its competitors, ads, scans and boards stay and become unassigned.</DialogDescription>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmDelete(null)}>Cancel</Button>
            <Button variant="destructive" disabled={removeClient.isPending} onClick={() => confirmDelete && removeClient.mutate(confirmDelete.id)}>
              {removeClient.isPending && <Loader2 className="animate-spin" />} Delete folder
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
