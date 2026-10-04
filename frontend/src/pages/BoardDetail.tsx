import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bookmark, CalendarDays, Download, FolderClosed, ImageOff, Loader2, Pencil, Tag, Trash2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { AdDetailSheet } from "@/components/ads/AdDetailSheet";
import { PlatformIcons } from "@/components/ads/PlatformIcons";
import { ScoreBadge, ScoreRing } from "@/components/ads/ScoreBadge";
import { EmptyState, ErrorState } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api, exportUrl, type BoardItem } from "@/lib/api";
import { cn, timeAgo, titleCase } from "@/lib/utils";
import { BoardFormDialog } from "./Boards";

function cleanTag(t: string) {
  return t.trim().toLowerCase().replace(/^#/, "").replace(/\s+/g, " ").slice(0, 32);
}

function TagEditor({ tags, onChange, suggestions }: { tags: string[]; onChange: (tags: string[]) => void; suggestions: string[] }) {
  const [value, setValue] = useState("");
  const add = (raw: string) => {
    const t = cleanTag(raw);
    if (t && !tags.includes(t)) onChange([...tags, t]);
    setValue("");
  };
  const listId = useId();
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {tags.map((t) => (
        <span key={t} className="inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-[11px]">
          #{t}
          <button type="button" aria-label={`Remove tag ${t}`} className="text-muted-foreground hover:text-foreground" onClick={() => onChange(tags.filter((x) => x !== t))}>
            <X className="size-3" />
          </button>
        </span>
      ))}
      <input
        list={listId}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === ",") && value.trim()) {
            e.preventDefault();
            add(value);
          } else if (e.key === "Backspace" && !value && tags.length) {
            onChange(tags.slice(0, -1));
          }
        }}
        onBlur={() => value.trim() && add(value)}
        placeholder={tags.length ? "Add tag" : "Add tags: hook, ugc, offer…"}
        aria-label="Add tag"
        className="h-6 min-w-24 flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
      />
      <datalist id={listId}>
        {suggestions.filter((s) => !tags.includes(s)).map((s) => <option key={s} value={s} />)}
      </datalist>
    </div>
  );
}

function ItemCard({
  item, boardId, onOpen, suggestions, index,
}: { item: BoardItem; boardId: number; onOpen: (id: number) => void; suggestions: string[]; index: number }) {
  const qc = useQueryClient();
  const [note, setNote] = useState(item.note ?? "");
  useEffect(() => setNote(item.note ?? ""), [item.note]);
  const [imgFailed, setImgFailed] = useState(false);
  const ad = item.ad;
  const src = ad.thumbnail_url || ad.screenshot_url;

  const update = useMutation({
    mutationFn: (body: { note?: string; tags?: string[] }) => api.updateBoardItem(boardId, item.id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["board", boardId] });
      qc.invalidateQueries({ queryKey: ["board-tags"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't save"),
  });
  const remove = useMutation({
    mutationFn: () => api.removeBoardItem(boardId, item.id),
    onSuccess: () => {
      toast("Removed from board");
      qc.invalidateQueries({ queryKey: ["board", boardId] });
      qc.invalidateQueries({ queryKey: ["boards"] });
    },
  });

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ delay: Math.min(index, 12) * 0.025 }}
      className="group mb-4 break-inside-avoid overflow-hidden rounded-xl border border-border bg-card"
    >
      <div className="relative">
        <button type="button" onClick={() => onOpen(ad.id)} className="block w-full">
          {src && !imgFailed ? (
            <img src={src} alt={ad.headline ?? `Ad ${ad.library_id}`} loading="lazy" onError={() => setImgFailed(true)} className="block max-h-[380px] w-full bg-muted object-cover object-top" />
          ) : (
            <div className="grid aspect-square place-items-center bg-muted text-muted-foreground"><ImageOff className="size-6" /></div>
          )}
        </button>
        <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between bg-gradient-to-b from-black/55 to-transparent p-2.5">
          <ScoreBadge badge={ad.badge} className="backdrop-blur-md" />
          <div className="rounded-full bg-black/50 p-0.5 backdrop-blur-md">
            <ScoreRing score={ad.score} badge={ad.badge} size={36} stroke={3.5} className="text-white" />
          </div>
        </div>
        <Button
          variant="secondary"
          size="icon-sm"
          aria-label="Remove from board"
          className="absolute right-2 bottom-2 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
          disabled={remove.isPending}
          onClick={() => remove.mutate()}
        >
          {remove.isPending ? <Loader2 className="animate-spin" /> : <Trash2 />}
        </Button>
      </div>
      <div className="space-y-2.5 p-3.5">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-semibold">{ad.page_name ?? "Unknown page"}</span>
          <PlatformIcons platforms={ad.platforms} />
        </div>
        {(ad.headline || ad.ad_copy) && <p className="line-clamp-2 text-[13px] text-muted-foreground">{ad.headline || ad.ad_copy}</p>}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1"><CalendarDays className="size-3.5" /><span className="num">{ad.days_running}d</span></span>
          <span className="rounded-md bg-muted px-1.5 py-0.5 text-[11px]">{titleCase(ad.media_type)}</span>
          <span className="ml-auto">saved {timeAgo(item.added_at)}</span>
        </div>
        <div className="rounded-lg border border-border bg-background/50 p-2 focus-within:border-ring">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onBlur={() => note !== (item.note ?? "") && update.mutate({ note })}
            placeholder="Why is this ad here? What would you steal?"
            aria-label="Note"
            maxLength={2000}
            rows={note ? Math.min(6, Math.max(2, Math.ceil(note.length / 42))) : 2}
            className="w-full resize-none bg-transparent text-[13px] leading-relaxed outline-none placeholder:text-muted-foreground"
          />
          <div className="mt-1 border-t border-border pt-1.5">
            <TagEditor tags={item.tags} suggestions={suggestions} onChange={(tags) => update.mutate({ tags })} />
          </div>
        </div>
        {update.isPending && <div className="flex items-center gap-1 text-[11px] text-muted-foreground"><Loader2 className="size-3 animate-spin" /> Saving…</div>}
      </div>
    </motion.article>
  );
}

export default function BoardDetail() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [tag, setTag] = useState<string | null>(null);
  const [openAd, setOpenAd] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const q = useQuery({ queryKey: ["board", id, tag], queryFn: () => api.board(id, tag ?? undefined) });
  const allTags = useQuery({ queryKey: ["board-tags"], queryFn: api.boardTags });
  const del = useMutation({
    mutationFn: () => api.deleteBoard(id),
    onSuccess: () => {
      toast.success("Board deleted");
      qc.invalidateQueries({ queryKey: ["boards"] });
      navigate("/boards");
    },
  });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const b = q.data;
  const suggestions = (allTags.data ?? []).map((t) => t.name);

  return (
    <>
      <Link to="/boards" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Swipe files
      </Link>
      {!b ? (
        <div className="space-y-4"><Skeleton className="h-10 w-72" /><div className="columns-1 gap-4 sm:columns-2 xl:columns-3 2xl:columns-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="mb-4 h-96" />)}</div></div>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
                <Bookmark className="size-5 text-primary" /> {b.name}
              </h1>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span><span className="num">{b.item_count}</span> ad{b.item_count !== 1 ? "s" : ""}</span>
                {b.client_name && (
                  <span className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-xs"><FolderClosed className="size-3" /> {b.client_name}</span>
                )}
                {b.description && <span className="max-w-xl">· {b.description}</span>}
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={!b.items.length} asChild={!!b.items.length}>
                {b.items.length ? (
                  <a href={exportUrl.adsCsv({ ids: b.items.map((i) => i.ad.id).join(",") })}><Download /> Export CSV</a>
                ) : (
                  <span><Download /> Export CSV</span>
                )}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}><Pencil /> Edit</Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)} aria-label="Delete board"><Trash2 /></Button>
            </div>
          </div>

          {b.tags.length > 0 && (
            <div className="mb-5 flex flex-wrap items-center gap-1.5">
              <Tag className="mr-1 size-4 text-muted-foreground" />
              <button type="button" onClick={() => setTag(null)} className={cn("rounded-full border px-2.5 py-1 text-xs", tag === null ? "border-primary bg-primary/10 text-foreground" : "border-border text-muted-foreground hover:text-foreground")}>
                All
              </button>
              {b.tags.map((t) => (
                <button key={t.name} type="button" onClick={() => setTag(tag === t.name ? null : t.name)} className={cn("rounded-full border px-2.5 py-1 text-xs", tag === t.name ? "border-primary bg-primary/10 text-foreground" : "border-border text-muted-foreground hover:text-foreground")}>
                  #{t.name} <span className="num opacity-60">{t.count}</span>
                </button>
              ))}
            </div>
          )}

          {!b.items.length ? (
            tag ? (
              <EmptyState icon={Tag} title={`No ads tagged #${tag}`} action={<Button variant="outline" onClick={() => setTag(null)}>Show all</Button>} />
            ) : (
              <EmptyState
                icon={Bookmark}
                title="This board is empty"
                description="Open the Results Gallery and use the bookmark button on any ad (or select several and choose “Save to board”)."
                action={<Button asChild><Link to="/ads">Browse ads</Link></Button>}
              />
            )
          ) : (
            <div className="columns-1 gap-4 sm:columns-2 xl:columns-3 2xl:columns-4">
              <AnimatePresence>
                {b.items.map((item, i) => (
                  <ItemCard key={item.id} item={item} boardId={b.id} onOpen={setOpenAd} suggestions={suggestions} index={i} />
                ))}
              </AnimatePresence>
            </div>
          )}
          {editing && <BoardFormDialog open={editing} onOpenChange={setEditing} board={b} />}
        </>
      )}

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="max-w-sm">
          <DialogTitle>Delete “{b?.name}”?</DialogTitle>
          <DialogDescription>The board, its notes and tags are deleted. The ads themselves stay in your library.</DialogDescription>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmDelete(false)}>Cancel</Button>
            <Button variant="destructive" disabled={del.isPending} onClick={() => del.mutate()}>
              {del.isPending && <Loader2 className="animate-spin" />} Delete board
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <AdDetailSheet adId={openAd} onClose={() => setOpenAd(null)} />
    </>
  );
}
