import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BellOff, CalendarClock, Eye, Info, Loader2, Pencil, Play, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AdDetailSheet } from "@/components/ads/AdDetailSheet";
import { CompetitorAvatar } from "@/components/CompetitorAvatar";
import { EmptyState, ErrorState, PageHeader } from "@/components/States";
import { StatusPill } from "@/components/StatusPill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import { ChangeFeed } from "@/components/watch/ChangeFeed";
import { ScheduleDialog } from "@/components/watch/ScheduleDialog";
import { api, type WatchItem } from "@/lib/api";
import { flag } from "@/lib/countries";
import { scheduleLabel, timeAgo, timeUntil } from "@/lib/utils";

function SummaryChips({ item }: { item: WatchItem }) {
  const s = item.last_scan?.change_summary;
  if (!item.last_scan) return <span className="text-xs text-muted-foreground">No scheduled run yet</span>;
  if (!s || (!s.baseline && s.new === undefined)) return <StatusPill status={item.last_scan.status} />;
  if (s.baseline) return <span className="text-xs text-muted-foreground">Baseline · {s.ads} ads</span>;
  return (
    <span className="num flex gap-2 text-xs">
      <span className="text-success">+{s.new} new</span>
      <span className="text-muted-foreground">{s.stopped} stopped</span>
      <span className="text-gold">{s.scaled} scaled</span>
    </span>
  );
}

function Row({ item, onEdit }: { item: WatchItem; onEdit: () => void }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const refresh = () => qc.invalidateQueries({ queryKey: ["watchlist"] });
  const update = useMutation({ mutationFn: (patch: Partial<WatchItem>) => api.watchUpdate(item.id, patch), onSuccess: refresh });
  const run = useMutation({
    mutationFn: () => api.watchRun(item.id),
    onSuccess: (r) => {
      refresh();
      toast.success(`Scanning ${item.competitor_name}`, { action: { label: "Watch live", onClick: () => navigate(`/scans/${r.scan_id}`) } });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't start"),
  });
  const remove = useMutation({ mutationFn: () => api.watchDelete(item.id), onSuccess: () => { refresh(); toast(`Stopped watching ${item.competitor_name}`); } });

  return (
    <div className="flex flex-wrap items-center gap-4 border-b border-border px-5 py-4 last:border-0">
      <Link to={`/competitors/${item.competitor_id}`} className="flex min-w-48 flex-1 items-center gap-3">
        <CompetitorAvatar name={item.competitor_name} src={item.competitor_logo} className="size-10 rounded-xl" />
        <div className="min-w-0">
          <div className="truncate font-medium">{item.competitor_name}</div>
          <div className="text-xs text-muted-foreground">{flag(item.country)} {item.search_type === "page_id" ? "Page ID" : "Keyword"} · max {item.max_ads}</div>
        </div>
      </Link>
      <div className="w-40">
        <div className="flex items-center gap-1.5 text-sm"><CalendarClock className="size-3.5 text-muted-foreground" /> {scheduleLabel(item)}</div>
        <div className="text-xs text-muted-foreground">{item.enabled ? (item.next_run_at ? `Next ${timeUntil(item.next_run_at)}` : "—") : "Paused"}</div>
      </div>
      <div className="w-48">
        <SummaryChips item={item} />
        <div className="text-xs text-muted-foreground">{item.last_run_at ? `Last run ${timeAgo(item.last_run_at)}` : "Never run"}</div>
      </div>
      <div className="flex items-center gap-1">
        <Tooltip content={item.enabled ? "Pause schedule" : "Resume schedule"}>
          <span className="px-1"><Switch checked={item.enabled} onCheckedChange={(v) => update.mutate({ enabled: v })} aria-label="Enabled" /></span>
        </Tooltip>
        <Tooltip content={item.notify ? "Alerts on" : "Alerts off"}>
          <Button variant="ghost" size="icon-sm" onClick={() => update.mutate({ notify: !item.notify })} aria-label="Toggle alerts">
            {item.notify ? <Bell className="text-primary" /> : <BellOff />}
          </Button>
        </Tooltip>
        <Tooltip content="Run now"><Button variant="ghost" size="icon-sm" onClick={() => run.mutate()} disabled={run.isPending} aria-label="Run now">{run.isPending ? <Loader2 className="animate-spin" /> : <Play />}</Button></Tooltip>
        <Tooltip content="Edit schedule"><Button variant="ghost" size="icon-sm" onClick={onEdit} aria-label="Edit"><Pencil /></Button></Tooltip>
        <Tooltip content="Remove from watchlist"><Button variant="ghost" size="icon-sm" onClick={() => remove.mutate()} aria-label="Remove"><Trash2 /></Button></Tooltip>
      </div>
    </div>
  );
}

export default function Watchlist() {
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<WatchItem | undefined>();
  const [openAd, setOpenAd] = useState<number | null>(null);
  const q = useQuery({ queryKey: ["watchlist"], queryFn: api.watchlist, refetchInterval: 30000 });
  const summary = useQuery({ queryKey: ["change-summary"], queryFn: () => api.changeSummary(30) });

  return (
    <>
      <PageHeader
        title="Watchlist"
        description="Competitors re-scanned on a schedule, and everything that changed."
        actions={<Button onClick={() => setAdding(true)}><Plus /> Watch competitor</Button>}
      />
      <div className="mb-5 flex items-start gap-2 rounded-xl border border-border bg-muted/40 px-4 py-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" />
        Schedules run while Ad Spy Engine is open (times are your computer's local time). If the app was closed at a scheduled time, that scan runs once as soon as you start it again.
      </div>
      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card className="self-start overflow-hidden">
          <CardHeader className="border-b border-border pb-4">
            <div><CardTitle>Schedules</CardTitle><CardDescription>{q.data?.length ?? 0} competitors watched</CardDescription></div>
          </CardHeader>
          {q.isError ? (
            <ErrorState className="m-5" error={q.error} onRetry={() => q.refetch()} />
          ) : q.isLoading ? (
            <div className="space-y-2 p-5">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
          ) : !q.data?.length ? (
            <EmptyState className="m-5" icon={Eye} title="Nothing on the watchlist" description="Watch a competitor to re-scan it daily or weekly and get alerted when they launch, stop or scale ads." action={<Button onClick={() => setAdding(true)}><Plus /> Watch competitor</Button>} />
          ) : (
            q.data.map((item) => <Row key={item.id} item={item} onEdit={() => setEditing(item)} />)
          )}
        </Card>
        <Card className="self-start">
          <CardHeader>
            <div>
              <CardTitle>Change feed</CardTitle>
              <CardDescription>
                Last 30 days: <span className="text-success">{summary.data?.new ?? 0} new</span> · {summary.data?.stopped ?? 0} stopped · <span className="text-gold">{summary.data?.scaled ?? 0} scaled</span>
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent><ChangeFeed onOpenAd={setOpenAd} /></CardContent>
        </Card>
      </div>
      <ScheduleDialog open={adding} onOpenChange={setAdding} />
      <ScheduleDialog open={!!editing} onOpenChange={(o) => !o && setEditing(undefined)} item={editing} />
      <AdDetailSheet adId={openAd} onClose={() => setOpenAd(null)} />
    </>
  );
}
