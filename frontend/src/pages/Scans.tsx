import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Download, History, Radar } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CompetitorAvatar } from "@/components/CompetitorAvatar";
import { EmptyState, ErrorState, PageHeader } from "@/components/States";
import { StatusPill } from "@/components/StatusPill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, exportUrl, type ScanStatus } from "@/lib/api";
import { flag } from "@/lib/countries";
import { cn, formatDate, formatDuration, timeAgo } from "@/lib/utils";

const FILTERS: (ScanStatus | "")[] = ["", "running", "completed", "blocked", "failed", "cancelled", "interrupted"];
const SIZE = 25;

export default function Scans() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<ScanStatus | "">("");
  const [page, setPage] = useState(0);
  const q = useQuery({
    queryKey: ["scans", status, page],
    queryFn: () => api.scans({ status: status || undefined, limit: SIZE, offset: page * SIZE }),
    refetchInterval: 10000,
  });
  const pages = Math.max(1, Math.ceil((q.data?.total ?? 0) / SIZE));

  return (
    <>
      <PageHeader
        title="Scan history"
        description="Every scan, its outcome and its log."
        actions={
          <Button asChild>
            <Link to="/scan/new">
              <Radar /> New scan
            </Link>
          </Button>
        }
      />
      <div className="mb-4 flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f || "all"}
            type="button"
            onClick={() => { setStatus(f); setPage(0); }}
            className={cn(
              "h-8 rounded-full border px-3 text-xs font-medium capitalize",
              status === f ? "border-primary/60 bg-primary/15" : "border-border text-muted-foreground hover:text-foreground",
            )}
          >
            {f || "All"}
          </button>
        ))}
      </div>
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.isLoading ? (
        <Card className="space-y-2 p-4">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</Card>
      ) : !q.data?.items.length ? (
        <EmptyState icon={History} title={status ? `No ${status} scans` : "No scans yet"} description="Scans you run appear here with their status, timing and log." />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] tracking-wide text-muted-foreground uppercase">
                  <th className="px-5 py-3 font-medium">#</th>
                  <th className="px-3 py-3 font-medium">Competitor</th>
                  <th className="px-3 py-3 font-medium">Filters</th>
                  <th className="px-3 py-3 font-medium">Status</th>
                  <th className="px-3 py-3 text-right font-medium">Ads</th>
                  <th className="px-3 py-3 text-right font-medium">New</th>
                  <th className="px-3 py-3 text-right font-medium">Failed</th>
                  <th className="px-3 py-3 text-right font-medium">Duration</th>
                  <th className="px-3 py-3 font-medium">Started</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {q.data.items.map((s) => (
                  <tr key={s.id} onClick={() => navigate(`/scans/${s.id}`)} className="cursor-pointer border-b border-border last:border-0 hover:bg-accent/50">
                    <td className="num px-5 py-3 text-muted-foreground">{s.id}</td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2.5">
                        <CompetitorAvatar name={s.competitor_name} src={s.competitor_logo} className="size-7" />
                        <div>
                          <div className="font-medium">{s.competitor_name}</div>
                          <div className="text-xs text-muted-foreground">{s.search_type === "page_id" ? "Page ID" : "Keyword"} · {s.query}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-xs text-muted-foreground">
                      {flag(s.country)} {s.country} · {s.media_type} · max {s.max_ads}
                      {s.exact_page && " · exact"}
                    </td>
                    <td className="px-3 py-3"><StatusPill status={s.status} /></td>
                    <td className="num px-3 py-3 text-right">{s.ads_found}</td>
                    <td className="num px-3 py-3 text-right text-success">{s.new_ads ? `+${s.new_ads}` : "0"}</td>
                    <td className={cn("num px-3 py-3 text-right", s.ads_failed ? "text-destructive" : "text-muted-foreground")}>{s.ads_failed}</td>
                    <td className="num px-3 py-3 text-right text-muted-foreground">{formatDuration(s.duration_seconds)}</td>
                    <td className="px-3 py-3 text-xs text-muted-foreground" title={formatDate(s.started_at)}>{timeAgo(s.started_at ?? s.created_at)}</td>
                    <td className="px-5 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      {s.ads_found > 0 && (
                        <Button variant="ghost" size="icon-sm" asChild aria-label="Export CSV">
                          <a href={exportUrl.scanCsv(s.id)}><Download /></a>
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t border-border px-5 py-3 text-xs text-muted-foreground">
            <span>{q.data.total} scans</span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="icon-sm" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft /></Button>
              <span className="num">{page + 1} / {pages}</span>
              <Button variant="outline" size="icon-sm" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight /></Button>
            </div>
          </div>
        </Card>
      )}
    </>
  );
}
