import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, Megaphone, Radar, Sparkles, Trophy, Zap } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartTooltip } from "@/components/charts/ChartTooltip";
import { CompetitorAvatar } from "@/components/CompetitorAvatar";
import { KpiCard } from "@/components/KpiCard";
import { BADGE_META } from "@/components/ads/ScoreBadge";
import { EmptyState, ErrorState, PageHeader } from "@/components/States";
import { StatusPill } from "@/components/StatusPill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type DashboardStats } from "@/lib/api";
import { flag } from "@/lib/countries";
import { formatDuration, formatNumber, timeAgo, titleCase } from "@/lib/utils";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function DiscoveredChart({ data }: { data: DashboardStats["ads_per_day"] }) {
  const fmt = (d: string | number) => new Date(`${d}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const total = data.reduce((a, b) => a + b.count, 0);
  return (
    <Card className="flex flex-col lg:col-span-2">
      <CardHeader>
        <div>
          <CardTitle>Ads discovered</CardTitle>
          <CardDescription>New ads first seen per day · last 14 days</CardDescription>
        </div>
        <div className="num text-right text-2xl font-semibold">{formatNumber(total)}</div>
      </CardHeader>
      <CardContent className="min-h-56 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.6} />
            <XAxis dataKey="date" tickFormatter={fmt} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} interval={1} />
            <YAxis allowDecimals={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: "var(--accent)" }} content={<ChartTooltip unit=" ads" labelFormat={fmt} />} />
            <Bar dataKey="count" fill="var(--primary)" radius={[4, 4, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

function Breakdown({ stats }: { stats: DashboardStats }) {
  const totalBadges = stats.badges.reduce((a, b) => a + b.count, 0) || 1;
  const maxFormat = Math.max(1, ...stats.formats.map((f) => f.count));
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Score distribution</CardTitle>
          <CardDescription>All tracked ads by Winner Score badge</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {stats.badges.map((b) => {
          const meta = BADGE_META[b.name];
          const Icon = meta.icon;
          const pct = (b.count / totalBadges) * 100;
          return (
            <div key={b.name}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="inline-flex items-center gap-1.5 font-medium">
                  <Icon className="size-3.5" style={{ color: meta.color }} /> {meta.label}
                </span>
                <span className="num text-muted-foreground">
                  {formatNumber(b.count)} · {pct.toFixed(0)}%
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: meta.color }} />
              </div>
            </div>
          );
        })}
        <div className="border-t border-border pt-3">
          <div className="mb-2 text-xs font-medium text-muted-foreground">Formats</div>
          {stats.formats.slice(0, 5).map((f) => (
            <div key={f.name} className="mb-1.5 grid grid-cols-[72px_1fr_36px] items-center gap-2 text-xs">
              <span>{titleCase(f.name)}</span>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary" style={{ width: `${(f.count / maxFormat) * 100}%` }} />
              </div>
              <span className="num text-right text-muted-foreground">{f.count}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function RecentScans({ stats }: { stats: DashboardStats }) {
  const navigate = useNavigate();
  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <div>
          <CardTitle>Recent scans</CardTitle>
          <CardDescription>Latest Ad Library scans</CardDescription>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link to="/scans">
            View all <ArrowRight />
          </Link>
        </Button>
      </CardHeader>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-y border-border text-left text-[11px] tracking-wide text-muted-foreground uppercase">
              <th className="px-5 py-2 font-medium">Competitor</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 text-right font-medium">Ads</th>
              <th className="px-3 py-2 text-right font-medium">New</th>
              <th className="px-3 py-2 text-right font-medium">Duration</th>
              <th className="px-5 py-2 text-right font-medium">When</th>
            </tr>
          </thead>
          <tbody>
            {stats.recent_scans.map((s) => (
              <tr key={s.id} onClick={() => navigate(`/scans/${s.id}`)} className="cursor-pointer border-b border-border last:border-0 hover:bg-accent/50">
                <td className="px-5 py-2.5">
                  <div className="flex items-center gap-2.5">
                    <CompetitorAvatar name={s.competitor_name} src={s.competitor_logo} className="size-7" />
                    <div className="min-w-0">
                      <div className="truncate font-medium">{s.competitor_name ?? s.query}</div>
                      <div className="text-xs text-muted-foreground">
                        {flag(s.country)} {s.search_type === "page_id" ? "Page ID" : "Keyword"} · {s.query}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <StatusPill status={s.status} />
                </td>
                <td className="num px-3 py-2.5 text-right">{s.ads_found}</td>
                <td className="num px-3 py-2.5 text-right text-success">{s.new_ads ? `+${s.new_ads}` : "0"}</td>
                <td className="num px-3 py-2.5 text-right text-muted-foreground">{formatDuration(s.duration_seconds)}</td>
                <td className="px-5 py-2.5 text-right text-xs text-muted-foreground">{timeAgo(s.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ActivityFeed({ stats }: { stats: DashboardStats }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Activity</CardTitle>
          <CardDescription>What changed recently</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <ol className="relative space-y-4 border-l border-border pl-5">
          {stats.activity.map((a) => (
            <li key={a.scan_id} className="relative">
              <span className="absolute top-1.5 -left-[25px] size-2.5 rounded-full border-2 border-background bg-primary" />
              <Link to={`/scans/${a.scan_id}`} className="block text-sm hover:text-primary">
                {a.status === "completed" ? (
                  <>
                    <span className="font-medium">{a.competitor_name}</span>{" "}
                    <span className="text-muted-foreground">— {a.new_ads > 0 ? `${a.new_ads} new ads found` : `${a.ads_found} ads re-checked`}</span>
                  </>
                ) : (
                  <>
                    <span className="font-medium">{a.competitor_name}</span> <span className="text-muted-foreground">— scan {a.status}</span>
                  </>
                )}
              </Link>
              <div className="text-xs text-muted-foreground">{timeAgo(a.at)}</div>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const { data, isLoading, isError, error, refetch } = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard, refetchInterval: 30000 });
  const k = data?.kpis;
  const empty = data && data.kpis.ads_tracked === 0 && data.recent_scans.length === 0;

  return (
    <>
      <PageHeader
        title={greeting()}
        description="Here's what your competitors are running on Meta right now."
        actions={
          <Button asChild>
            <Link to="/scan/new">
              <Radar /> New scan
            </Link>
          </Button>
        }
      />
      {isError && <ErrorState error={error} onRetry={() => refetch()} />}
      {empty ? (
        <EmptyState
          icon={Sparkles}
          title="No scans yet"
          description="Enter a competitor's brand name or Facebook Page ID and Ad Spy Engine will collect, screenshot and score every active ad."
          action={
            <Button asChild size="lg">
              <Link to="/scan/new">
                <Radar /> Run your first scan
              </Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <KpiCard index={0} label="Ads tracked" value={k?.ads_tracked} icon={Megaphone} loading={isLoading} hint={k && `${formatNumber(k.active_ads)} active · ${k.competitors} competitors`} />
            <KpiCard index={1} label="Active scans" value={k?.active_scans} icon={Activity} tone="info" loading={isLoading} hint={data?.avg_ads_per_minute ? `~${data.avg_ads_per_minute} ads/min throughput` : "Idle"} />
            <KpiCard index={2} label="Winners found" value={k?.winners} icon={Trophy} tone="gold" loading={isLoading} hint="Winner Score ≥ 75" />
            <KpiCard index={3} label="New ads this week" value={k?.new_this_week} icon={Zap} tone="success" loading={isLoading} hint="First seen in the last 7 days" />
          </div>
          {isLoading || !data ? (
            <div className="grid gap-5 lg:grid-cols-3">
              <Skeleton className="h-72 lg:col-span-2" />
              <Skeleton className="h-72" />
            </div>
          ) : (
            <>
              <div className="grid gap-5 lg:grid-cols-3">
                <DiscoveredChart data={data.ads_per_day} />
                <Breakdown stats={data} />
              </div>
              <div className="grid gap-5 lg:grid-cols-3">
                <RecentScans stats={data} />
                <ActivityFeed stats={data} />
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
