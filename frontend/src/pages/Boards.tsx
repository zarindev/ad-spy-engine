import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, FolderClosed, ImageOff, Loader2, Plus } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { EmptyState, ErrorState, PageHeader } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input, Label } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Board } from "@/lib/api";
import { timeAgo } from "@/lib/utils";

function Mosaic({ covers }: { covers: string[] }) {
  if (!covers.length) {
    return (
      <div className="grid aspect-[16/9] place-items-center bg-muted text-muted-foreground">
        <ImageOff className="size-6" />
      </div>
    );
  }
  const cells = covers.slice(0, 4);
  return (
    <div className={`grid aspect-[16/9] gap-0.5 bg-border ${cells.length > 1 ? "grid-cols-2" : ""} ${cells.length > 2 ? "grid-rows-2" : ""}`}>
      {cells.map((src, i) => (
        <img
          key={src + i}
          src={src}
          alt=""
          loading="lazy"
          className={`size-full bg-muted object-cover object-top ${cells.length === 3 && i === 0 ? "row-span-2" : ""}`}
          onError={(e) => (e.currentTarget.style.visibility = "hidden")}
        />
      ))}
    </div>
  );
}

export function BoardFormDialog({
  open, onOpenChange, board,
}: { open: boolean; onOpenChange: (o: boolean) => void; board?: Board }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const clients = useQuery({ queryKey: ["clients"], queryFn: api.clients, enabled: open });
  const [name, setName] = useState(board?.name ?? "");
  const [description, setDescription] = useState(board?.description ?? "");
  const [clientId, setClientId] = useState<number | null>(board?.client_id ?? null);

  const save = useMutation({
    mutationFn: () =>
      board
        ? api.updateBoard(board.id, { name: name.trim(), description, client_id: clientId, clear_client: clientId === null })
        : api.createBoard({ name: name.trim(), description: description || undefined, client_id: clientId }),
    onSuccess: (b) => {
      qc.invalidateQueries({ queryKey: ["boards"] });
      qc.invalidateQueries({ queryKey: ["board", b.id] });
      onOpenChange(false);
      if (!board) {
        toast.success(`Created “${b.name}”`, { description: "Save ads to it from the Results Gallery or any ad's detail panel." });
        navigate(`/boards/${b.id}`);
      }
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't save the board"),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogTitle>{board ? "Edit board" : "New swipe file board"}</DialogTitle>
        <DialogDescription>Collect ads worth copying, with notes and tags for your team.</DialogDescription>
        <form
          className="mt-2 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) save.mutate();
          }}
        >
          <div>
            <Label htmlFor="board-name">Name</Label>
            <Input id="board-name" className="mt-1.5" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} placeholder="e.g. UGC hooks, Q4 offers" autoFocus />
          </div>
          <div>
            <Label htmlFor="board-desc">Description <span className="font-normal text-muted-foreground">(optional)</span></Label>
            <textarea
              id="board-desc"
              className="mt-1.5 min-h-20 w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
              value={description}
              maxLength={500}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this board for?"
            />
          </div>
          <div>
            <Label htmlFor="board-client">Client folder <span className="font-normal text-muted-foreground">(optional)</span></Label>
            <select
              id="board-client"
              className="mt-1.5 h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm"
              value={clientId ?? ""}
              onChange={(e) => setClientId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">No client</option>
              {clients.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={!name.trim() || save.isPending}>
              {save.isPending && <Loader2 className="animate-spin" />} {board ? "Save" : "Create board"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function Boards() {
  const q = useQuery({ queryKey: ["boards"], queryFn: api.boards });
  const [creating, setCreating] = useState(false);
  return (
    <>
      <PageHeader
        title="Swipe Files"
        description="Boards of ads worth stealing from, with your notes and tags."
        actions={<Button onClick={() => setCreating(true)}><Plus /> New board</Button>}
      />
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="aspect-[4/3]" />)}</div>
      ) : !q.data?.length ? (
        <EmptyState
          icon={Bookmark}
          title="No swipe files yet"
          description="Create a board, then use the bookmark button on any ad to save it. Add notes and tags so your team knows why it's there."
          action={
            <div className="flex gap-2">
              <Button onClick={() => setCreating(true)}><Plus /> New board</Button>
              <Button variant="outline" asChild><Link to="/ads">Browse ads</Link></Button>
            </div>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {q.data.map((b, i) => (
            <motion.div key={b.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
              <Link to={`/boards/${b.id}`}>
                <Card className="group overflow-hidden transition-all hover:-translate-y-0.5 hover:border-primary/40">
                  <Mosaic covers={b.covers} />
                  <div className="space-y-1 p-4">
                    <div className="truncate font-semibold">{b.name}</div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="num">{b.item_count}</span> ad{b.item_count !== 1 ? "s" : ""}
                      <span>·</span> updated {timeAgo(b.updated_at)}
                    </div>
                    {b.client_name && (
                      <div className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                        <FolderClosed className="size-3" /> {b.client_name}
                      </div>
                    )}
                  </div>
                </Card>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
      {creating && <BoardFormDialog open={creating} onOpenChange={setCreating} />}
    </>
  );
}
