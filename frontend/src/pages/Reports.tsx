import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Download, ExternalLink, FileText, Loader2, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { EmptyState, ErrorState, PageHeader } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input, Label } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { api, type Report } from "@/lib/api";
import { cn, formatDate, timeAgo } from "@/lib/utils";

const SECTIONS = [
  { key: "summary", label: "Executive KPIs", hint: "Ads collected, winners, average lifespan" },
  { key: "charts", label: "Format & placement breakdown", hint: "Where and how they advertise" },
  { key: "top_ads", label: "Top ads with screenshots", hint: "Ranked by Winner Score" },
  { key: "all_ads", label: "Full ad table", hint: "Every ad in the scan" },
];

function Step({ n, title, done, children }: { n: number; title: string; done?: boolean; children: React.ReactNode }) {
  return (
    <div className="relative pl-10">
      <span className={cn("absolute top-0 left-0 grid size-7 place-items-center rounded-full border text-xs font-semibold", done ? "border-primary bg-primary text-white" : "border-border bg-card")}>
        {done ? <Check className="size-3.5" /> : n}
      </span>
      <div className="mb-3 pt-1 text-sm font-semibold">{title}</div>
      {children}
    </div>
  );
}

export default function Reports() {
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const competitors = useQuery({ queryKey: ["competitors"], queryFn: api.competitors });
  const reports = useQuery({ queryKey: ["reports"], queryFn: api.reports });
  const preset = params.get("scan") ? Number(params.get("scan")) : null;
  const presetScan = useQuery({ queryKey: ["scan", preset], queryFn: () => api.scan(preset!), enabled: !!preset });

  const [competitorId, setCompetitorId] = useState<number | null>(null);
  const [scanId, setScanId] = useState<number | null>(preset);
  const [sections, setSections] = useState(SECTIONS.map((s) => s.key));
  const [topN, setTopN] = useState(24);
  const [title, setTitle] = useState("");
  const [pdf, setPdf] = useState(true);
  const [preview, setPreview] = useState<Report | null>(null);

  useEffect(() => {
    if (presetScan.data) setCompetitorId(presetScan.data.competitor_id);
  }, [presetScan.data]);

  const scans = useQuery({
    queryKey: ["scans", "for-competitor", competitorId],
    queryFn: () => api.scans({ competitor_id: competitorId!, limit: 30 }),
    enabled: !!competitorId,
  });
  const usableScans = useMemo(() => (scans.data?.items ?? []).filter((s) => s.ads_found > 0), [scans.data]);
  useEffect(() => {
    if (competitorId && usableScans.length && !usableScans.some((s) => s.id === scanId)) setScanId(usableScans[0].id);
  }, [competitorId, usableScans, scanId]);

  const generate = useMutation({
    mutationFn: () => api.createReport({ scan_id: scanId!, title: title.trim() || undefined, sections, top_n: topN, pdf }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["reports"] });
      if (r.status === "failed") toast.error("Report failed", { description: r.error ?? undefined });
      else {
        toast.success("Report ready");
        setPreview(r);
      }
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Report failed"),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteReport(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reports"] }),
  });

  return (
    <>
      <PageHeader title="Reports" description="Turn a scan into a client-ready report — HTML and PDF." />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Generate a report</CardTitle>
              <CardDescription>Pick a competitor, the scan, and what to include.</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-7">
            <Step n={1} title="Competitor" done={!!competitorId}>
              {competitors.isLoading ? (
                <Skeleton className="h-10" />
              ) : !competitors.data?.length ? (
                <p className="text-sm text-muted-foreground">Run a scan first — competitors appear here.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {competitors.data.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => { setCompetitorId(c.id); setScanId(null); }}
                      className={cn("h-8 rounded-full border px-3 text-xs font-medium", competitorId === c.id ? "border-primary/60 bg-primary/15" : "border-border text-muted-foreground hover:text-foreground")}
                    >
                      {c.name} <span className="num ml-1 text-muted-foreground">{c.ad_count}</span>
                    </button>
                  ))}
                </div>
              )}
            </Step>
            <Step n={2} title="Scan" done={!!scanId}>
              {!competitorId ? (
                <p className="text-sm text-muted-foreground">Choose a competitor first.</p>
              ) : scans.isLoading ? (
                <Skeleton className="h-10" />
              ) : !usableScans.length ? (
                <p className="text-sm text-muted-foreground">No scans with ads for this competitor.</p>
              ) : (
                <div className="space-y-1.5">
                  {usableScans.slice(0, 6).map((s) => (
                    <label key={s.id} className={cn("flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm", scanId === s.id ? "border-primary/60 bg-primary/10" : "border-border hover:bg-accent/40")}>
                      <input type="radio" className="accent-[var(--primary)]" checked={scanId === s.id} onChange={() => setScanId(s.id)} />
                      <span className="font-medium">#{s.id}</span>
                      <span className="text-muted-foreground">{s.query} · {s.country}</span>
                      <span className="num ml-auto text-xs">{s.ads_found} ads · {formatDate(s.started_at)}</span>
                    </label>
                  ))}
                </div>
              )}
            </Step>
            <Step n={3} title="Sections" done={sections.length > 0}>
              <div className="grid gap-2 sm:grid-cols-2">
                {SECTIONS.map((s) => (
                  <label key={s.key} className="flex cursor-pointer items-start gap-3 rounded-lg border border-border p-3 hover:bg-accent/40">
                    <Checkbox
                      className="mt-0.5"
                      checked={sections.includes(s.key)}
                      onCheckedChange={(v) => setSections(v ? [...sections, s.key] : sections.filter((x) => x !== s.key))}
                    />
                    <span>
                      <span className="block text-sm font-medium">{s.label}</span>
                      <span className="block text-xs text-muted-foreground">{s.hint}</span>
                    </span>
                  </label>
                ))}
              </div>
              {sections.includes("top_ads") && (
                <div className="mt-4">
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-muted-foreground">Top ads to feature</span>
                    <span className="num font-medium">{topN}</span>
                  </div>
                  <Slider min={3} max={60} step={3} value={[topN]} onValueChange={([v]) => setTopN(v)} />
                </div>
              )}
            </Step>
            <Step n={4} title="Finish">
              <div className="space-y-3">
                <div>
                  <Label htmlFor="rtitle">Report title (optional)</Label>
                  <Input id="rtitle" className="mt-1.5" placeholder="Defaults to the competitor name" value={title} onChange={(e) => setTitle(e.target.value)} />
                </div>
                <label className="flex items-center justify-between rounded-lg border border-border p-3">
                  <span className="text-sm">Also export PDF <span className="text-xs text-muted-foreground">(headless Chrome, ~5s)</span></span>
                  <Switch checked={pdf} onCheckedChange={setPdf} />
                </label>
                <Button size="lg" className="w-full" disabled={!scanId || !sections.length || generate.isPending} onClick={() => generate.mutate()}>
                  {generate.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}
                  {generate.isPending ? "Generating…" : "Generate report"}
                </Button>
              </div>
            </Step>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Report history</CardTitle>
              <CardDescription>Preview in-app or download.</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {reports.isError ? (
              <ErrorState error={reports.error} onRetry={() => reports.refetch()} />
            ) : reports.isLoading ? (
              <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
            ) : !reports.data?.length ? (
              <EmptyState icon={FileText} title="No reports yet" description="Generated reports are saved here with HTML and PDF versions." />
            ) : (
              <div className="space-y-2">
                {reports.data.map((r) => (
                  <div key={r.id} className="flex items-center gap-3 rounded-lg border border-border p-3">
                    <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary/12 text-primary">
                      <FileText className="size-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{r.title}</div>
                      <div className="text-xs text-muted-foreground">
                        Scan #{r.scan_id} · {timeAgo(r.created_at)} · {(r.options.sections ?? []).length} sections
                      </div>
                    </div>
                    {r.status === "failed" ? (
                      <Badge variant="destructive" title={r.error ?? ""}>Failed</Badge>
                    ) : (
                      <div className="flex gap-1">
                        <Button variant="outline" size="sm" onClick={() => setPreview(r)}>Preview</Button>
                        {r.pdf_url && (
                          <Button variant="outline" size="icon-sm" asChild aria-label="Download PDF">
                            <a href={r.pdf_url} download><Download /></a>
                          </Button>
                        )}
                      </div>
                    )}
                    <Button variant="ghost" size="icon-sm" aria-label="Delete report" onClick={() => remove.mutate(r.id)}>
                      <Trash2 />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="flex h-[90vh] max-w-6xl flex-col p-0">
          <div className="flex items-center gap-3 border-b border-border px-5 py-3 pr-14">
            <div className="min-w-0 flex-1">
              <DialogTitle className="truncate text-base">{preview?.title}</DialogTitle>
              <DialogDescription className="mt-0 text-xs">Preview</DialogDescription>
            </div>
            {preview?.html_url && (
              <Button variant="outline" size="sm" asChild>
                <a href={preview.html_url} target="_blank" rel="noreferrer"><ExternalLink /> Open HTML</a>
              </Button>
            )}
            {preview?.pdf_url && (
              <Button size="sm" asChild>
                <a href={preview.pdf_url} download><Download /> PDF</a>
              </Button>
            )}
          </div>
          {preview?.html_url && <iframe title="Report preview" src={preview.html_url} className="w-full flex-1 rounded-b-2xl bg-[#0B0B12]" />}
        </DialogContent>
      </Dialog>
    </>
  );
}
