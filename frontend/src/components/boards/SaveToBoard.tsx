import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, BookmarkCheck, Check, Loader2, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Bookmark button + popover that toggles an ad (or several) in swipe file boards. */
export function SaveToBoard({
  adIds, variant = "outline", size = "sm", className, label = "Save", onDone,
}: {
  adIds: number[];
  variant?: "outline" | "ghost" | "default" | "secondary";
  size?: "sm" | "icon-sm" | "default";
  className?: string;
  label?: string;
  onDone?: () => void;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const single = adIds.length === 1 ? adIds[0] : null;
  const boards = useQuery({ queryKey: ["boards"], queryFn: api.boards, enabled: open });
  const saved = useQuery({
    queryKey: ["boards-for-ad", single],
    queryFn: () => api.boardsForAd(single!),
    enabled: open && single !== null,
  });
  const savedSet = new Set(saved.data ?? []);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["boards"] });
    qc.invalidateQueries({ queryKey: ["board"] });
    if (single !== null) qc.invalidateQueries({ queryKey: ["boards-for-ad", single] });
  };

  const toggle = useMutation({
    mutationFn: async ({ boardId, on }: { boardId: number; on: boolean }) => {
      if (on) return api.addToBoard(boardId, adIds);
      await api.removeAdFromBoard(boardId, single!);
      return null;
    },
    onSuccess: (res, { boardId, on }) => {
      const board = boards.data?.find((b) => b.id === boardId);
      if (on) {
        const n = res?.added ?? 0;
        toast.success(n ? `Saved to ${board?.name ?? "board"}` : `Already in ${board?.name ?? "board"}`, {
          description: adIds.length > 1 ? `${n} of ${adIds.length} ads added` : undefined,
        });
        onDone?.();
      } else {
        toast(`Removed from ${board?.name ?? "board"}`);
      }
      refresh();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't update the board"),
  });

  const create = useMutation({
    mutationFn: () => api.createBoard({ name: name.trim(), ad_ids: adIds }),
    onSuccess: (b) => {
      toast.success(`Created “${b.name}”`, { description: `${b.item_count} ad${b.item_count !== 1 ? "s" : ""} saved` });
      setName("");
      refresh();
      onDone?.();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't create the board"),
  });

  const isSaved = single !== null && savedSet.size > 0;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant={variant} size={size} className={className} aria-label="Save to swipe file">
          {isSaved ? <BookmarkCheck className="text-primary" /> : <Bookmark />}
          {size !== "icon-sm" && label}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 p-0" onClick={(e) => e.stopPropagation()}>
        <div className="border-b border-border px-3 py-2.5">
          <div className="text-sm font-semibold">Save to swipe file</div>
          <div className="text-xs text-muted-foreground">{adIds.length > 1 ? `${adIds.length} selected ads` : "Pick one or more boards"}</div>
        </div>
        <div className="max-h-64 overflow-y-auto p-1.5">
          {boards.isLoading ? (
            <div className="flex items-center gap-2 px-2 py-3 text-xs text-muted-foreground"><Loader2 className="size-3.5 animate-spin" /> Loading boards…</div>
          ) : boards.isError ? (
            <div className="px-2 py-3 text-xs text-destructive">Couldn't load boards.</div>
          ) : !boards.data?.length ? (
            <div className="px-2 py-3 text-xs text-muted-foreground">No boards yet. Create your first one below.</div>
          ) : (
            boards.data.map((b) => {
              const on = savedSet.has(b.id);
              const busy = toggle.isPending && toggle.variables?.boardId === b.id;
              return (
                <button
                  key={b.id}
                  type="button"
                  disabled={busy}
                  onClick={() => toggle.mutate({ boardId: b.id, on: single === null ? true : !on })}
                  className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent"
                >
                  <span className={cn("grid size-4 shrink-0 place-items-center rounded border", on ? "border-primary bg-primary text-primary-foreground" : "border-border")}>
                    {busy ? <Loader2 className="size-3 animate-spin" /> : on && <Check className="size-3" />}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{b.name}</span>
                  <span className="num text-xs text-muted-foreground">{b.item_count}</span>
                </button>
              );
            })
          )}
        </div>
        <form
          className="flex gap-1.5 border-t border-border p-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="New board name" className="h-8 text-sm" maxLength={80} />
          <Button type="submit" size="sm" className="h-8" disabled={!name.trim() || create.isPending}>
            {create.isPending ? <Loader2 className="animate-spin" /> : <Plus />} Add
          </Button>
        </form>
        <Link to="/boards" className="block border-t border-border px-3 py-2 text-xs text-muted-foreground hover:text-foreground" onClick={() => setOpen(false)}>
          Open swipe files →
        </Link>
      </PopoverContent>
    </Popover>
  );
}
