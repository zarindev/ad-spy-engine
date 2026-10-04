import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight, ChevronDown, Download, FileText, Loader2, RotateCcw, ShieldAlert, Square, Terminal, TriangleAlert, XCircle,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { AdDetailSheet } from "@/components/ads/AdDetailSheet";
import { ScoreRing } from "@/components/ads/ScoreBadge";
import { CompetitorAvatar } from "@/components/CompetitorAvatar";
import { ProgressRing } from "@/components/ProgressRing";
import { EmptyState, ErrorState } from "@/components/States";
import { StatusPill } from "@/components/StatusPill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useScanEvents } from "@/hooks/useScanEvents";
import { api, exportUrl, FINISHED, type Ad, type Scan } from "@/lib/api";
import { countryName, flag } from "@/lib/countries";
import { cn, formatDuration, formatNumber, parseDate } from "@/lib/utils";

const STAGES: Record<string, string> = {
  queued: "Waiting in queue",
  rate_limited: "Pausing between scans",
  running: "Starting",
  starting_browser: "Launching Chrome",
  loading: "Opening the Ad Library",
  scrolling: "Collecting ads",
};

function useElapsed(scan: Scan | undefined, live: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [live]);
  if (!scan?.started_at) return null;
  const start = parseDate(scan.started_at)!.getTime();
  const end = scan.finished_at ? parseDate(scan.finished_at)!.getTime() : now;
  return Math.max(0, (end - start) / 1000);
}

function Counter({ label, value, tone }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className="rounded-xl bg-muted/50 px-4 py-3">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <motion.div key={String(value)} initial={{ opacity: 0.4, y: -3 }} animate={{ opacity: 1, y: 0 }} className={cn("num text-2xl font-semibold", tone)}>
        {value}
      </motion.div>
    </div>
  );
}

function LogConsole({ scanId, lines, live }: { scanId: number; lines: { id: number; level: string; message: string; ts: number }[]; live: boolean }) {
  const [open, setOpen] = useState(true);
  const fileLog = useQuery({ queryKey: ["scan-log", scanId], queryFn: () => api.scanLog(scanId), enabled: !live && open });
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Scroll only the console, never the page.
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [lines.length, fileLog.data, open]);
  const fromFile = !live && fileLog.data;
  return (
    <Card className="overflow-hidden">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-4 py-3 text-sm font-medium hover:bg-accent/40">
        <Terminal className="size-4 text-muted-foreground" /> Live log
        {live && <span className="size-1.5 animate-pulse rounded-full bg-success" />}
        <ChevronDown className={cn("ml-auto size-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div ref={box} className="num max-h-72 overflow-y-auto border-t border-border bg-black/40 px-4 py-3 text-[12px] leading-relaxed">
          {fromFile
            ? fileLog.data!.split("\n").map((l, i) => (
                <div key={i} className={cn("whitespace-pre-wrap text-muted-foreground", /WARNING|ERROR/.test(l) && "text-warning")}>
                  {l.replace(/^\S+ \S+ \| /, "")}
                </div>
              ))
            : lines.map((l) => (
                <div key={l.id} className={cn("flex gap-3", l.level === "warning" ? "text-warning" : l.level === "error" ? "text-destructive" : "text-muted-foreground")}>
                  <span className="shrink-0 text-muted-foreground/60">{new Date(l.ts * 1000).toLocaleTimeString()}</span>
                  <span className="whitespace-pre-wrap">{l.message}</span>
                </div>
              ))}
          {live && !lines.length && <div className="text-muted-foreground">Waiting for the worker…</div>}
        </div>
      )}
    </Card>
  );
}

function OutcomeBanner({ scan, blocked }: { scan: Scan; blocked: { reason: string; suggestions: string[] } | null }) {
  if (scan.status === "blocked") {
    const suggestions = blocked?.suggestions ?? [
      "Wait 15–30 minutes before scanning again.",
      "Switch to visible mode in Settings to see what Meta shows.",
      "Try the undetected driver in Settings → Scraping.",
    ];
    return (
      <div className="rounded-xl border border-warning/40 bg-warning/10 p-4">
        <div className="flex items-center gap-2 font-medium text-warning">
          <ShieldAlert className="size-4" /> Meta blocked this scan
        </div>
        <p className="mt-1 text-sm">{scan.block_reason}</p>
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-muted-foreground">
          {suggestions.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-muted-foreground">Ad Spy Engine never logs in or solves captchas — the ads collected before the block are kept.</p>
      </div>
    );
  }
  if (scan.status === "failed" || scan.status === "interrupted") {
    return (
      <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4">
        <div className="flex items-center gap-2 font-medium text-destructive">
          {scan.status === "failed" ? <XCircle className="size-4" /> : <TriangleAlert className="size-4" />}
          Scan {scan.status}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{scan.error ?? "See the log below for details."}</p>
      </div>
    );
  }
  return null;
}

export default function LiveScan() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [openAd, setOpenAd] = useState<number | null>(null);

  const scanQ = useQuery({
    queryKey: ["scan", id],
    queryFn: () => api.scan(id),
    refetchInterval: (q) => (q.state.data && FINISHED.includes(q.state.data.status) ? false : 4000),
  });
  const scan = scanQ.data;
  const live = !!scan && !FINISHED.includes(scan.status);
  const ev = useScanEvents(id, live);

  useEffect(() => {
    if (ev.finished) {
      qc.invalidateQueries({ queryKey: ["scan", id] });
      qc.invalidateQueries({ queryKey: ["scan-ads", id] });
    }
  }, [ev.finished, id, qc]);

  const adsQ = useQuery({
    queryKey: ["scan-ads", id],
    queryFn: () => api.ads({ scan_id: id, sort: "first_seen", limit: 120 }),
    enabled: !!scan,
  });

  const ads: Ad[] = useMemo(() => {
    const map = new Map<number, Ad>();
    ev.liveAds.forEach((a) => map.set(a.id, a));
    adsQ.data?.items.forEach((a) => map.has(a.id) || map.set(a.id, a));
    return [...map.values()];
  }, [ev.liveAds, adsQ.data]);

  const elapsed = useElapsed(scan, live);
  const cancel = useMutation({
    mutationFn: () => api.cancelScan(id),
    onSuccess: () => toast("Cancelling scan…", { description: "Finishing the current ad, then stopping." }),
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't cancel"),
  });
  const rerun = useMutation({
    mutationFn: () => api.rerunScan(id),
    onSuccess: (s) => navigate(`/scans/${s.id}`),
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't start"),
  });

  if (scanQ.isError) return <ErrorState error={scanQ.error} onRetry={() => scanQ.refetch()} />;
  if (!scan) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-12 w-1/3" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  const found = live ? (ev.progress?.found ?? scan.ads_found) : scan.ads_found;
  const failed = live ? (ev.progress?.failed ?? scan.ads_failed) : scan.ads_failed;
  const total = ev.progress?.total ?? scan.total_results;
  const target = Math.max(1, Math.min(scan.max_ads, total ?? scan.max_ads));
  const pct = scan.status === "completed" ? 1 : found / target;
  const stage = live ? (STAGES[ev.status ?? scan.status] ?? "Working") : null;
  const rate = elapsed && found ? (found / elapsed) * 60 : null;

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <CompetitorAvatar name={scan.competitor_name} src={scan.competitor_logo} className="size-12 rounded-xl" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <h1 className="truncate text-2xl font-semibold tracking-tight">{scan.competitor_name ?? scan.query}</h1>
            <StatusPill status={scan.status} />
          </div>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Scan #{scan.id} · {scan.search_type === "page_id" ? "Page ID" : "Keyword"} “{scan.query}” · {flag(scan.country)} {countryName(scan.country)} · {scan.media_type} media
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {live ? (
            <Button variant="outline" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
              {cancel.isPending ? <Loader2 className="animate-spin" /> : <Square />} Cancel
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => rerun.mutate()} disabled={rerun.isPending}>
                <RotateCcw /> Re-run
              </Button>
              {scan.ads_found > 0 && (
                <>
                  <Button variant="outline" asChild>
                    <a href={exportUrl.scanCsv(scan.id)}>
                      <Download /> CSV
                    </a>
                  </Button>
                  <Button variant="outline" asChild>
                    <Link to={`/reports?scan=${scan.id}`}>
                      <FileText /> Report
                    </Link>
                  </Button>
                  <Button asChild>
                    <Link to={`/ads?scan=${scan.id}`}>
                      View results <ArrowRight />
                    </Link>
                  </Button>
                </>
              )}
            </>
          )}
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card className="flex flex-col items-center p-6">
            <ProgressRing value={pct} live={live}>
              <div>
                <div className="num text-4xl font-semibold">{found}</div>
                <div className="text-xs text-muted-foreground">of {formatNumber(target)} ads</div>
              </div>
            </ProgressRing>
            <div className="mt-4 h-5 text-sm font-medium">
              {stage && (
                <span className="inline-flex items-center gap-2 text-primary">
                  <Loader2 className="size-4 animate-spin" /> {stage}…
                </span>
              )}
              {!live && scan.status === "completed" && <span className="text-success">Scan complete</span>}
            </div>
            <div className="mt-5 grid w-full grid-cols-2 gap-2">
              <Counter label="Found" value={found} />
              <Counter label="New" value={live ? "…" : scan.new_ads} tone="text-success" />
              <Counter label="Failed" value={failed} tone={failed ? "text-destructive" : undefined} />
              <Counter label="Elapsed" value={formatDuration(elapsed)} />
            </div>
            <div className="mt-4 w-full space-y-1 text-xs text-muted-foreground">
              <div className="flex justify-between">
                <span>Meta's estimate</span>
                <span className="num">{total !== null && total !== undefined ? `~${formatNumber(total)} ads` : "—"}</span>
              </div>
              <div className="flex justify-between">
                <span>Throughput</span>
                <span className="num">{rate ? `${rate.toFixed(0)} ads/min` : "—"}</span>
              </div>
            </div>
          </Card>
          <OutcomeBanner scan={scan} blocked={ev.blocked} />
        </div>

        <div className="min-w-0 space-y-5">
          <Card className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="text-sm font-semibold">
                {live ? "Ads arriving live" : "Collected ads"}{" "}
                <span className="num ml-1 text-muted-foreground">
                  {live ? ads.length : (adsQ.data?.total ?? ads.length)}
                  {!live && (adsQ.data?.total ?? 0) > ads.length && ` · showing ${ads.length}`}
                </span>
              </div>
              {!live && ads.length > 0 && (
                <Link to={`/ads?scan=${scan.id}`} className="text-xs text-primary hover:underline">
                  Open gallery →
                </Link>
              )}
            </div>
            {ads.length === 0 ? (
              live ? (
                <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
                  {Array.from({ length: 12 }).map((_, i) => (
                    <Skeleton key={i} className="aspect-[4/5]" />
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={TriangleAlert}
                  title="No ads collected"
                  description={scan.status === "completed" ? "Meta returned no ads for this search. Try another country, ‘All countries’, or a Page ID." : "The scan ended before any ads were collected."}
                />
              )
            ) : (
              <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-5 2xl:grid-cols-6">
                <AnimatePresence initial={false}>
                  {ads.map((ad) => (
                    <motion.button
                      layout
                      key={ad.id}
                      type="button"
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      onClick={() => setOpenAd(ad.id)}
                      className="group relative aspect-[4/5] overflow-hidden rounded-lg border border-border bg-muted text-left"
                    >
                      {(ad.thumbnail_url || ad.screenshot_url) && (
                        <img src={(ad.thumbnail_url ?? ad.screenshot_url)!} alt="" loading="lazy" className="size-full object-cover object-top transition-transform group-hover:scale-105" />
                      )}
                      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between bg-gradient-to-t from-black/80 to-transparent p-1.5">
                        <span className="num text-[10px] font-medium text-white">{ad.days_running}d</span>
                        <ScoreRing score={ad.score} badge={ad.badge} size={28} stroke={2.5} className="rounded-full bg-black/60 text-white" />
                      </div>
                    </motion.button>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </Card>
          <LogConsole scanId={scan.id} lines={ev.logs} live={live} />
        </div>
      </div>
      <AdDetailSheet adId={openAd} onClose={() => setOpenAd(null)} />
    </>
  );
}
