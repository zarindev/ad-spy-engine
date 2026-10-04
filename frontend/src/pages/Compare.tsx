import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Columns3, Crown, FileText, ImageOff, Lightbulb, Plus, Sparkles, X } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { HOOK_LABELS } from "@/components/ai/AnalysisCards";
import { ScoreBadge } from "@/components/ads/ScoreBadge";
import { AdDetailSheet } from "@/components/ads/AdDetailSheet";
import { BarList } from "@/components/charts/BarList";
import { ChartTooltip } from "@/components/charts/ChartTooltip";
import { CompetitorAvatar } from "@/components/CompetitorAvatar";
import { EmptyState, ErrorState, PageHeader } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type Ad, type BrandStats, type BrandSummary } from "@/lib/api";
import { cn, formatNumber, timeAgo, titleCase } from "@/lib/utils";

const MAX = 3;

type Metric = { key: keyof BrandStats; label: string; hint?: string; suffix?: string; best: "high" | "low" | null };
const METRICS: Metric[] = [
  { key: "ads", label: "Ads analyzed", best: null },
  { key: "active", label: "Active now", best: null },
  { key: "winners", label: "Winners", best: "high" },
  { key: "winner_rate", label: "Winner rate", suffix: "%", hint: "Share of ads scoring 75+", best: "high" },
  { key: "avg_score", label: "Avg. Winner Score", best: "high" },
  { key: "median_days", label: "Median days running", best: "high" },
  { key: "max_days", label: "Longest-running ad", suffix: " d", best: "high" },
  { key: "launched_30d", label: "Launched in last 30 days", best: "high" },
  { key: "variation_groups", label: "Concepts with variations", hint: "Groups of ads sharing a creative or copy", best: null },
  { key: "largest_group", label: "Most-tested concept", suffix: " ads", best: null },
];

function bestIndex(brands: BrandSummary[], m: Metric): number | null {
  if (!m.best || brands.length < 2) return null;
  const values = brands.map((b) => Number(b.stats[m.key]));
  const target = m.best === "high" ? Math.max(...values) : Math.min(...values);
  const hits = values.filter((v) => v === target).length;
  return hits === 1 ? values.indexOf(target) : null;
}

function Thumb({ ad, onOpen }: { ad: Ad; onOpen: (id: number) => void }) {
  const [failed, setFailed] = useState(false);
  const src = ad.thumbnail_url || ad.screenshot_url;
  return (
    <button type="button" onClick={() => onOpen(ad.id)} className="group/t relative overflow-hidden rounded-lg border border-border bg-muted text-left">
      {src && !failed ? (
        <img src={src} alt={ad.headline ?? `Ad ${ad.library_id}`} loading="lazy" onError={() => setFailed(true)} className="aspect-square w-full object-cover object-top transition-transform group-hover/t:scale-[1.03]" />
      ) : (
        <div className="grid aspect-square place-items-center text-muted-foreground"><ImageOff className="size-5" /></div>
      )}
      <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/70 to-transparent p-1.5 text-[11px] text-white">
        <ScoreBadge badge={ad.badge} className="scale-90" />
        <span className="num">{ad.days_running}d</span>
      </div>
    </button>
  );
}

function Cadence({ brand }: { brand: BrandSummary }) {
  const total = brand.cadence.reduce((a, w) => a + w.launched, 0);
  const fmt = (w: string | number) => new Date(String(w)).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-xs">
        <span className="font-medium">{brand.name}</span>
        <span className="text-muted-foreground"><span className="num text-foreground">{total}</span> in 12 weeks</span>
      </div>
      <div className="h-24">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={brand.cadence} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <XAxis dataKey="week" hide />
            <Tooltip cursor={{ fill: "var(--accent)" }} content={<ChartTooltip unit=" launched" labelFormat={(l) => `Week of ${fmt(l)}`} />} />
            <Bar dataKey="launched" fill="var(--primary)" radius={[3, 3, 0, 0]} maxBarSize={18} minPointSize={1} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function Compare() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const ids = (params.get("ids") ?? "").split(",").map(Number).filter((n) => n > 0).slice(0, MAX);
  const ownOnly = params.get("own") !== "0";
  const [openAd, setOpenAd] = useState<number | null>(null);
  const competitors = useQuery({ queryKey: ["competitors"], queryFn: api.competitors });
  const clients = useQuery({ queryKey: ["clients"], queryFn: api.clients });
  const q = useQuery({ queryKey: ["compare", ids.join(","), ownOnly], queryFn: () => api.compare(ids, ownOnly), enabled: ids.length > 0 });

  const update = (nextIds: number[], own = ownOnly) => {
    const next = new URLSearchParams(params);
    if (nextIds.length) next.set("ids", nextIds.join(","));
    else next.delete("ids");
    if (own) next.delete("own");
    else next.set("own", "0");
    setParams(next, { replace: true });
  };
  const available = (competitors.data ?? []).filter((c) => c.ad_count > 0 && !ids.includes(c.id));
  const byId = new Map((competitors.data ?? []).map((c) => [c.id, c]));
  const brands = q.data?.brands ?? [];
  // Brand columns side by side from md up; stacked on phones.
  const cols = { "--cols": `repeat(${Math.max(ids.length, 1)}, minmax(0, 1fr))` } as React.CSSProperties;
  const analyzed = brands.some((b) => (b.insights.analyzed ?? 0) >= 5);

  return (
    <>
      <PageHeader
        title="Compare"
        description="Two or three competitors side by side: volume, longevity, creative mix and their best ads."
        actions={
          <>
            <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm" title="Keyword scans also return other advertisers that mention a brand">
              <Switch checked={ownOnly} onCheckedChange={(v) => update(ids, v)} aria-label="Only the brand's own pages" />
              Brand's own ads only
            </label>
            <Button disabled={ids.length < 2} onClick={() => navigate(`/reports?compare=${ids.join(",")}`)}>
              <FileText /> Comparison report
            </Button>
          </>
        }
      />

      <div className="mb-6 grid gap-3 md:grid-cols-3">
        {Array.from({ length: MAX }).map((_, slot) => {
          const id = ids[slot];
          const c = id ? byId.get(id) : undefined;
          const summary = brands.find((b) => b.id === id);
          if (id) {
            return (
              <Card key={slot} className="flex items-center gap-3 p-4">
                <CompetitorAvatar name={c?.name ?? "?"} src={c?.logo_url} className="size-11 rounded-xl" />
                <div className="min-w-0 flex-1">
                  <Link to={`/competitors/${id}`} className="flex items-center gap-1 truncate font-semibold hover:text-primary">
                    {c?.name ?? `Competitor ${id}`} <ArrowUpRight className="size-3.5 opacity-60" />
                  </Link>
                  <div className="truncate text-xs text-muted-foreground">
                    Last scan {timeAgo(c?.last_scan_at ?? null)}
                    {summary && summary.stats.other_advertisers_excluded > 0 && ` · ${summary.stats.other_advertisers_excluded} other-advertiser ads hidden`}
                  </div>
                </div>
                <Button variant="ghost" size="icon-sm" aria-label={`Remove ${c?.name ?? "competitor"}`} onClick={() => update(ids.filter((x) => x !== id))}><X /></Button>
              </Card>
            );
          }
          const isNext = slot === ids.length;
          return (
            <DropdownMenu key={slot}>
              <DropdownMenuTrigger asChild disabled={!isNext}>
                <button
                  type="button"
                  className={cn(
                    "flex min-h-[78px] items-center justify-center gap-2 rounded-xl border border-dashed border-border text-sm text-muted-foreground transition-colors",
                    isNext ? "hover:border-primary/50 hover:text-foreground" : "opacity-40",
                  )}
                >
                  <Plus className="size-4" /> {slot === 0 ? "Pick a competitor" : "Add competitor"}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="max-h-80 w-72 overflow-y-auto">
                {(clients.data ?? []).filter((cl) => cl.competitor_ids.length >= 2).length > 0 && ids.length === 0 && (
                  <>
                    <DropdownMenuLabel>Client folders</DropdownMenuLabel>
                    {(clients.data ?? []).filter((cl) => cl.competitor_ids.length >= 2).map((cl) => (
                      <DropdownMenuItem key={`cl-${cl.id}`} onSelect={() => update(cl.competitor_ids.slice(0, MAX))}>
                        <Columns3 /> {cl.name} <span className="ml-auto text-xs text-muted-foreground">{Math.min(cl.competitor_ids.length, MAX)} brands</span>
                      </DropdownMenuItem>
                    ))}
                  </>
                )}
                <DropdownMenuLabel>Competitors</DropdownMenuLabel>
                {available.length ? (
                  available.map((c) => (
                    <DropdownMenuItem key={c.id} onSelect={() => update([...ids, c.id])}>
                      <CompetitorAvatar name={c.name} src={c.logo_url} className="size-5 rounded" />
                      <span className="flex-1 truncate">{c.name}</span>
                      <span className="num text-xs text-muted-foreground">{c.ad_count}</span>
                    </DropdownMenuItem>
                  ))
                ) : (
                  <div className="px-2 py-2 text-xs text-muted-foreground">No other scanned competitors.</div>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          );
        })}
      </div>

      {!ids.length ? (
        <EmptyState
          icon={Columns3}
          title="Pick two or three competitors"
          description="See who keeps ads running longest, who launches most and which formats survive, then turn it into a branded report."
          action={!competitors.data?.length ? <Button asChild><Link to="/scan/new">Scan a competitor</Link></Button> : undefined}
        />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.isLoading || !q.data ? (
        <div className="space-y-4"><Skeleton className="h-40" /><Skeleton className="h-80" /><Skeleton className="h-64" /></div>
      ) : (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
          {(q.data.highlights.length > 0 || q.data.opportunities.length > 0) && (
            <div className="grid gap-6 xl:grid-cols-2">
              <Card>
                <CardHeader>
                  <div>
                    <CardTitle className="flex items-center gap-2"><Sparkles className="size-4 text-primary" /> Highlights</CardTitle>
                    <CardDescription>Measured differences between these brands</CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  {q.data.highlights.length ? (
                    <ul className="space-y-2.5 text-sm">
                      {q.data.highlights.map((h) => (
                        <li key={h} className="flex gap-2.5"><span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />{h}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground">Add a second competitor with at least 5 ads to see differences.</p>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <div>
                    <CardTitle className="flex items-center gap-2"><Lightbulb className="size-4 text-primary" /> Opportunities</CardTitle>
                    <CardDescription>Patterns in their long-running ads, each with its evidence</CardDescription>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {q.data.opportunities.length ? (
                    q.data.opportunities.map((o) => (
                      <div key={o.title} className="rounded-lg border border-border p-3">
                        <div className="text-sm font-medium">{o.title}</div>
                        <p className="mt-0.5 text-[13px] text-muted-foreground">{o.detail}</p>
                        <div className="mt-1 text-[11px] text-muted-foreground/80">Evidence: {o.evidence}</div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground">Not enough data yet. Scan more ads from these brands.</p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Scoreboard</CardTitle>
                <CardDescription>The leader on each row is marked with a crown when there's a single leader</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Metric</th>
                    {brands.map((b) => (
                      <th key={b.id} className="py-2 pr-4 text-right font-medium">
                        <span className="inline-flex items-center gap-2"><CompetitorAvatar name={b.name} src={b.logo} className="size-5 rounded" />{b.name}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {METRICS.map((m) => {
                    const best = bestIndex(brands, m);
                    return (
                      <tr key={m.key} className="border-b border-border/60 last:border-0">
                        <td className="py-2.5 pr-4">
                          <div>{m.label}</div>
                          {m.hint && <div className="text-[11px] text-muted-foreground">{m.hint}</div>}
                        </td>
                        {brands.map((b, i) => (
                          <td key={b.id} className={cn("num py-2.5 pr-4 text-right", best === i ? "font-semibold text-foreground" : "text-muted-foreground")}>
                            <span className="inline-flex items-center gap-1.5">
                              {best === i && <Crown className="size-3.5 text-gold" aria-label="Leader" />}
                              {formatNumber(Number(b.stats[m.key]))}{m.suffix ?? ""}
                            </span>
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Creative mix</CardTitle>
                <CardDescription>Share of each brand's ads</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="formats">
                <TabsList className="mb-4 flex-wrap">
                  <TabsTrigger value="formats">Formats</TabsTrigger>
                  <TabsTrigger value="winner_formats">Winners' formats</TabsTrigger>
                  <TabsTrigger value="placements">Placements</TabsTrigger>
                  <TabsTrigger value="longevity">Longevity</TabsTrigger>
                  <TabsTrigger value="ctas">Calls to action</TabsTrigger>
                  {analyzed && <TabsTrigger value="hooks">Hooks (AI)</TabsTrigger>}
                </TabsList>
                {(["formats", "winner_formats", "placements", "longevity", "ctas"] as const).map((key) => (
                  <TabsContent key={key} value={key}>
                    <div className="grid gap-6 md:[grid-template-columns:var(--cols)]" style={cols}>
                      {brands.map((b) => (
                        <div key={b.id} className="min-w-0">
                          <div className="mb-3 flex items-baseline justify-between text-xs">
                            <span className="font-medium">{b.name}</span>
                            <span className="num text-muted-foreground">{key === "winner_formats" ? b.stats.winners : b.stats.ads} ads</span>
                          </div>
                          <BarList
                            items={b[key]}
                            total={key === "winner_formats" ? b.stats.winners : b.stats.ads}
                            labelWidth="w-24"
                            format={key === "longevity" || key === "ctas" ? (s) => s : titleCase}
                          />
                        </div>
                      ))}
                    </div>
                  </TabsContent>
                ))}
                {analyzed && (
                  <TabsContent value="hooks">
                    <div className="grid gap-6 md:[grid-template-columns:var(--cols)]" style={cols}>
                      {brands.map((b) => (
                        <div key={b.id} className="min-w-0">
                          <div className="mb-3 flex items-baseline justify-between text-xs">
                            <span className="font-medium">{b.name}</span>
                            <span className="num text-muted-foreground">{b.insights.analyzed ?? 0} analyzed</span>
                          </div>
                          {(b.insights.analyzed ?? 0) ? (
                            <BarList items={b.insights.hook_distribution ?? []} labelWidth="w-24" format={(s) => HOOK_LABELS[s] ?? titleCase(s)} />
                          ) : (
                            <p className="text-sm text-muted-foreground">Not analyzed yet.</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </TabsContent>
                )}
              </Tabs>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Launch cadence</CardTitle>
                <CardDescription>New ads per week by start date, last 12 weeks. Each brand on its own scale.</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-6 md:[grid-template-columns:var(--cols)]" style={cols}>
                {brands.map((b) => <Cadence key={b.id} brand={b} />)}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Their best ads</CardTitle>
                <CardDescription>Top 4 by Winner Score. Click to open.</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-6 md:[grid-template-columns:var(--cols)]" style={cols}>
                {brands.map((b) => (
                  <div key={b.id} className="min-w-0">
                    <div className="mb-2 flex items-center justify-between text-xs">
                      <span className="font-medium">{b.name}</span>
                      <Link to={`/ads?competitor=${b.id}`} className="text-muted-foreground hover:text-foreground">All ads →</Link>
                    </div>
                    {b.top_ads.length ? (
                      <div className="grid grid-cols-2 gap-2">{b.top_ads.map((ad) => <Thumb key={ad.id} ad={ad} onOpen={setOpenAd} />)}</div>
                    ) : (
                      <p className="text-sm text-muted-foreground">No ads.</p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
      <AdDetailSheet adId={openAd} onClose={() => setOpenAd(null)} />
    </>
  );
}
