import { useInfiniteQuery } from "@tanstack/react-query";
import { CirclePause, Loader2, Sparkle, TrendingUp, Zap } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type ChangeItem, type ChangeKind } from "@/lib/api";
import { cn, timeAgo } from "@/lib/utils";

export const CHANGE_META: Record<ChangeKind, { label: string; icon: typeof Zap; variant: "success" | "muted" | "winner" }> = {
  new: { label: "New", icon: Sparkle, variant: "success" },
  stopped: { label: "Stopped", icon: CirclePause, variant: "muted" },
  scaled: { label: "Scaled", icon: TrendingUp, variant: "winner" },
};

function describe(c: ChangeItem): string {
  if (c.kind === "scaled") return `Variations ${c.details.from} → ${c.details.to}`;
  if (c.kind === "stopped") return `Stopped after ${c.details.days_running ?? c.ad.days_running} days`;
  return `Launched ${c.ad.days_running <= 1 ? "today" : `${c.ad.days_running} days ago`}`;
}

export function ChangeFeed({ competitorId, onOpenAd, compact, pageSize = 20 }: { competitorId?: number; onOpenAd: (id: number) => void; compact?: boolean; pageSize?: number }) {
  const [kind, setKind] = useState<ChangeKind | "">("");
  const q = useInfiniteQuery({
    queryKey: ["changes", competitorId, kind],
    queryFn: ({ pageParam }) => api.changes({ competitor_id: competitorId, kind, limit: pageSize, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const n = pages.reduce((a, p) => a + p.items.length, 0);
      return n < last.total ? n : undefined;
    },
  });
  const items = q.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {(["", "new", "stopped", "scaled"] as const).map((k) => (
          <button
            key={k || "all"}
            type="button"
            onClick={() => setKind(k)}
            className={cn("h-7 rounded-full border px-3 text-xs font-medium", kind === k ? "border-primary/60 bg-primary/15" : "border-border text-muted-foreground hover:text-foreground")}
          >
            {k ? CHANGE_META[k].label : "All changes"}
          </button>
        ))}
      </div>
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : !items.length ? (
        <EmptyState
          icon={Zap}
          title={kind ? `No ${CHANGE_META[kind].label.toLowerCase()} ads yet` : "No changes detected yet"}
          description="Changes appear after a competitor is scanned at least twice — new launches, stopped ads and ads gaining variations."
          className="py-10"
        />
      ) : (
        <div className="space-y-1.5">
          {items.map((c) => {
            const meta = CHANGE_META[c.kind];
            const Icon = meta.icon;
            return (
              <button key={c.id} type="button" onClick={() => onOpenAd(c.ad.id)} className="flex w-full items-center gap-3 rounded-lg border border-transparent p-2 text-left hover:border-border hover:bg-accent/40">
                <div className="size-12 shrink-0 overflow-hidden rounded-lg border border-border bg-muted">
                  {(c.ad.thumbnail_url || c.ad.screenshot_url) && <img src={(c.ad.thumbnail_url ?? c.ad.screenshot_url)!} alt="" loading="lazy" className="size-full object-cover" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Badge variant={meta.variant}><Icon /> {meta.label}</Badge>
                    {!compact && <span className="truncate text-sm font-medium">{c.competitor_name}</span>}
                  </div>
                  <div className="mt-0.5 truncate text-xs text-muted-foreground">
                    {describe(c)} · {c.ad.headline || c.ad.ad_copy || `Ad ${c.ad.library_id}`}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="num text-sm font-semibold">{c.ad.score}</div>
                  <div className="text-[11px] text-muted-foreground">{timeAgo(c.created_at)}</div>
                </div>
              </button>
            );
          })}
          {q.hasNextPage && (
            <Button variant="ghost" size="sm" className="w-full" onClick={() => q.fetchNextPage()} disabled={q.isFetchingNextPage}>
              {q.isFetchingNextPage && <Loader2 className="animate-spin" />} Load more
            </Button>
          )}
        </div>
      )}
      {compact && !!items.length && (
        <Link to="/watchlist" className="mt-2 block text-center text-xs text-primary hover:underline">Open watchlist →</Link>
      )}
    </div>
  );
}
