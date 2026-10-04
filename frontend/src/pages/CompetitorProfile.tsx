import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BrainCircuit, Layers, Lightbulb, Radar, RefreshCw, Trophy } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { HOOK_LABELS } from "@/components/ai/AnalysisCards";
import { AiAnalyzeButton } from "@/components/ai/AiAnalyzeButton";
import { AdDetailSheet } from "@/components/ads/AdDetailSheet";
import { AdCard } from "@/components/ads/AdCard";
import { BarList } from "@/components/charts/BarList";
import { ChartTooltip } from "@/components/charts/ChartTooltip";
import { CompetitorAvatar } from "@/components/CompetitorAvatar";
import { KpiCard } from "@/components/KpiCard";
import { ErrorState } from "@/components/States";
import { StatusPill } from "@/components/StatusPill";
import { ChangeFeed } from "@/components/watch/ChangeFeed";
import { WatchButton } from "@/components/watch/WatchButton";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type CompetitorProfile as Profile } from "@/lib/api";
import { formatNumber, timeAgo, titleCase } from "@/lib/utils";

function Timeline({ data }: { data: Profile["timeline"] }) {
  const [metric, setMetric] = useState<"launched" | "running">("launched");
  const fmt = (d: string | number) => new Date(`${d}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return (
    <Card className="flex flex-col lg:col-span-2">
      <CardHeader>
        <div>
          <CardTitle>Ad activity timeline</CardTitle>
          <CardDescription>{metric === "launched" ? "New ads launched per week (by start date)" : "Ads running each week"} · last 26 weeks</CardDescription>
        </div>
        <Tabs value={metric} onValueChange={(v) => setMetric(v as typeof metric)}>
          <TabsList>
            <TabsTrigger value="launched">Launches</TabsTrigger>
            <TabsTrigger value="running">Running</TabsTrigger>
          </TabsList>
        </Tabs>
      </CardHeader>
      <CardContent className="min-h-60 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.6} />
            <XAxis dataKey="week" tickFormatter={fmt} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} interval={3} />
            <YAxis allowDecimals={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: "var(--accent)" }} content={<ChartTooltip unit=" ads" labelFormat={(l) => `Week of ${fmt(l)}`} />} />
            <Bar dataKey={metric} fill="var(--primary)" radius={[4, 4, 0, 0]} maxBarSize={22} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

function Insights({ p, competitorId }: { p: Profile; competitorId: number }) {
  const ins = p.insights;
  if (!ins.analyzed) {
    return (
      <Card className="flex flex-col items-center justify-center p-6 text-center">
        <div className="mb-3 grid size-12 place-items-center rounded-2xl bg-primary/15 text-primary"><BrainCircuit className="size-6" /></div>
        <div className="font-semibold">Hooks & angles</div>
        <p className="mt-1 mb-4 max-w-xs text-sm text-muted-foreground">Let Claude read the copy and map their hook types, angles, offers and the ideas worth stealing.</p>
        <AiAnalyzeButton scope={{ competitor_id: competitorId, limit: 100 }} allowWinnersToggle />
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle className="flex items-center gap-2"><BrainCircuit className="size-4 text-primary" /> Hooks & angles</CardTitle>
          <CardDescription>AI analysis of {ins.analyzed} ads</CardDescription>
        </div>
        <AiAnalyzeButton scope={{ competitor_id: competitorId, limit: 300 }} label="Analyze more" size="sm" allowWinnersToggle />
      </CardHeader>
      <CardContent className="space-y-5">
        <div>
          <div className="mb-2 text-xs font-medium text-muted-foreground">Hook types</div>
          <BarList items={ins.hook_distribution ?? []} format={(s) => HOOK_LABELS[s] ?? titleCase(s)} />
        </div>
        <div>
          <div className="mb-2 text-xs font-medium text-muted-foreground">Top angles</div>
          <BarList items={ins.top_angles ?? []} format={(s) => s.charAt(0).toUpperCase() + s.slice(1)} labelWidth="w-44" max={6} />
        </div>
        {!!ins.recurring_offers?.length && (
          <div>
            <div className="mb-2 text-xs font-medium text-muted-foreground">Recurring offers</div>
            <div className="flex flex-wrap gap-1.5">
              {ins.recurring_offers.map((o) => <span key={o.name} className="rounded-full border border-border px-2.5 py-1 text-xs">{o.name} <span className="num text-muted-foreground">×{o.count}</span></span>)}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function CompetitorProfile() {
  const id = Number(useParams().id);
  const [openAd, setOpenAd] = useState<number | null>(null);
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["competitor-profile", id], queryFn: () => api.competitorProfile(id) });
  const regroup = useMutation({ mutationFn: () => api.regroup(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["competitor-profile", id] }) });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <div className="space-y-4"><Skeleton className="h-16 w-1/2" /><Skeleton className="h-28" /><Skeleton className="h-72" /></div>;
  const p = q.data;
  const c = p.competitor;
  const steal = p.insights.steal_ideas ?? [];

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <CompetitorAvatar name={c.name} src={c.logo_url} className="size-14 rounded-2xl" />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-tight">{c.name}</h1>
          <p className="text-sm text-muted-foreground">Last scanned {timeAgo(c.last_scan_at)}{c.page_id ? ` · Page ID ${c.page_id}` : ""}</p>
        </div>
        <div className="flex gap-2">
          <WatchButton competitorId={c.id} />
          <Button variant="outline" asChild><Link to={`/scan/new?q=${encodeURIComponent(c.page_id ?? c.name)}${c.page_id ? "&type=page_id" : ""}`}><Radar /> Scan again</Link></Button>
          <Button asChild><Link to={`/ads?competitor=${c.id}`}>All ads <ArrowRight /></Link></Button>
        </div>
      </div>

      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <KpiCard index={0} label="Ads tracked" value={c.ad_count} icon={Layers} hint={`${c.active_ads} active now`} />
          <KpiCard index={1} label="Winners" value={c.winners} icon={Trophy} tone="gold" hint={`Avg. score ${c.avg_score}`} />
          <KpiCard index={2} label="Avg. lifespan (days)" value={Math.round(c.avg_days_running)} icon={RefreshCw} tone="info" hint={`Longest ${c.max_days_running} days`} />
          <KpiCard index={3} label="Variation groups" value={p.group_count} icon={Layers} tone="success" hint="Creatives being iterated" />
        </div>

        <div className="grid gap-5 lg:grid-cols-3">
          <Timeline data={p.timeline} />
          <Insights p={p} competitorId={id} />
        </div>

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {(
            [
              ["Formats", p.formats, titleCase, "Share of ads"],
              ["Placements", p.placements, titleCase, "% of ads shown on each placement"],
              ["Calls to action", p.ctas, (s: string) => s, "Share of ads"],
              ["Lifespan", p.longevity, (s: string) => s, "Days running"],
            ] as const
          ).map(([title, items, fmt, hint]) => (
            <Card key={title}>
              <CardHeader><div><CardTitle>{title}</CardTitle><CardDescription>{hint}</CardDescription></div></CardHeader>
              <CardContent><BarList items={items} format={fmt} labelWidth="w-24" total={c.ad_count} /></CardContent>
            </Card>
          ))}
        </div>

        {!!steal.length && (
          <Card>
            <CardHeader><div><CardTitle className="flex items-center gap-2"><Lightbulb className="size-4 text-gold" /> Ideas worth stealing</CardTitle><CardDescription>From their highest-scoring analyzed ads</CardDescription></div></CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              {steal.map((s) => (
                <button key={s.ad_id} type="button" onClick={() => setOpenAd(s.ad_id)} className="flex gap-3 rounded-lg border border-border p-3 text-left hover:border-gold/40">
                  <span className="num grid size-9 shrink-0 place-items-center rounded-lg bg-gold/12 text-sm font-semibold text-gold">{s.score}</span>
                  <span>
                    <span className="block text-sm">{s.idea}</span>
                    {s.hook && <span className="mt-0.5 block truncate text-xs text-muted-foreground italic">“{s.hook}”</span>}
                  </span>
                </button>
              ))}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Variation groups</CardTitle>
              <CardDescription>{p.group_count} groups of ads sharing a creative or near-identical copy — where they're iterating</CardDescription>
            </div>
            <Button variant="ghost" size="sm" disabled={regroup.isPending} onClick={() => regroup.mutate()}><RefreshCw className={regroup.isPending ? "animate-spin" : ""} /> Regroup</Button>
          </CardHeader>
          <CardContent>
            {!p.groups.length ? (
              <p className="text-sm text-muted-foreground">No variation groups found — each ad is unique.</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                {p.groups.map((g) => (
                  <Link key={g.key} to={`/ads?competitor=${id}&group=${encodeURIComponent(g.key)}`} className="group flex gap-3 rounded-xl border border-border p-2.5 hover:border-primary/40">
                    <div className="relative size-20 shrink-0 overflow-hidden rounded-lg bg-muted">
                      {(g.lead.thumbnail_url || g.lead.screenshot_url) && <img src={(g.lead.thumbnail_url ?? g.lead.screenshot_url)!} alt="" className="size-full object-cover" loading="lazy" />}
                      <span className="num absolute top-1 left-1 rounded bg-black/70 px-1 text-[10px] text-white">×{g.size}</span>
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold">{g.label}</div>
                      <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{g.lead.headline || g.lead.ad_copy}</div>
                      <div className="num mt-1 text-[11px] text-muted-foreground">best {g.best_score} · up to {g.max_days}d</div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <div>
          <h2 className="mb-3 text-sm font-semibold">Top ads</h2>
          <div className="columns-1 gap-4 sm:columns-2 xl:columns-4">
            {p.top_ads.map((ad, i) => <AdCard key={ad.id} ad={ad} index={i} onOpen={(a) => setOpenAd(a.id)} />)}
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><div><CardTitle>Changes</CardTitle><CardDescription>What changed between scans</CardDescription></div></CardHeader>
          <CardContent><ChangeFeed competitorId={id} onOpenAd={setOpenAd} compact pageSize={8} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Scan history</CardTitle></CardHeader>
          <CardContent className="space-y-1">
            {p.recent_scans.map((s) => (
              <Link key={s.id} to={`/scans/${s.id}`} className="flex items-center justify-between rounded-lg px-2 py-2 text-sm hover:bg-accent/50">
                <span>#{s.id} · {s.query} · {s.country}</span>
                <span className="flex items-center gap-3"><span className="num text-xs text-muted-foreground">{formatNumber(s.ads_found)} ads · {timeAgo(s.started_at)}</span><StatusPill status={s.status} /></span>
              </Link>
            ))}
          </CardContent>
        </Card>
        </div>
      </div>
      <AdDetailSheet adId={openAd} onClose={() => setOpenAd(null)} />
    </>
  );
}
