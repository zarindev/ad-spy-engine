import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, Bot, Check, Columns3, Download, ExternalLink, FileText, FolderClosed, Loader2, Palette, ScanSearch, Sparkles, Trash2, User,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { CompetitorAvatar } from "@/components/CompetitorAvatar";
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
import { api, type Report, type ReportKind } from "@/lib/api";
import { cn, formatDate, timeAgo } from "@/lib/utils";

const SECTIONS = [
  { key: "cover", label: "Cover page", hint: "Your logo, client name and the brands covered" },
  { key: "summary", label: "Executive summary", hint: "Key numbers and findings" },
  { key: "winners", label: "Top winners", hint: "Best ads with screenshots" },
  { key: "charts", label: "Format & angle charts", hint: "Formats, placements, CTAs, cadence" },
  { key: "changes", label: "Change log", hint: "New, stopped and scaled ads" },
  { key: "opportunities", label: "Opportunities for you", hint: "What to test next" },
  { key: "appendix", label: "Appendix: all ads", hint: "Full table, up to 300 rows" },
];
const DEFAULT_SECTIONS = SECTIONS.filter((s) => s.key !== "appendix").map((s) => s.key);

type Scope = "client" | "competitors" | "scan";
const KIND_LABEL: Record<string, string> = { client: "Client", compare: "Comparison", competitor: "Competitor", scan: "Scan" };

function Step({ n, title, done, children, aside }: { n: number; title: string; done?: boolean; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="relative pl-10">
      <span className={cn("absolute top-0 left-0 grid size-7 place-items-center rounded-full border text-xs font-semibold", done ? "border-primary bg-primary text-white" : "border-border bg-card")}>
        {done ? <Check className="size-3.5" /> : n}
      </span>
      <div className="mb-3 flex items-center justify-between gap-2 pt-1">
        <span className="text-sm font-semibold">{title}</span>
        {aside}
      </div>
      {children}
    </div>
  );
}

function Chip({ active, onClick, children, disabled }: { active: boolean; onClick: () => void; children: React.ReactNode; disabled?: boolean }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors disabled:opacity-40",
        active ? "border-primary/60 bg-primary/15 text-foreground" : "border-border text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

export default function Reports() {
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const competitors = useQuery({ queryKey: ["competitors"], queryFn: api.competitors });
  const clients = useQuery({ queryKey: ["clients"], queryFn: api.clients });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const reports = useQuery({ queryKey: ["reports"], queryFn: api.reports });

  const presetScan = params.get("scan") ? Number(params.get("scan")) : null;
  const presetClient = params.get("client") ? Number(params.get("client")) : null;
  const presetIds = (params.get("compare") ?? params.get("competitor") ?? "").split(",").map(Number).filter((n) => n > 0);

  const [scope, setScope] = useState<Scope>(presetScan ? "scan" : presetClient ? "client" : presetIds.length ? "competitors" : "client");
  const [clientId, setClientId] = useState<number | null>(presetClient);
  const [picked, setPicked] = useState<number[]>(presetIds.slice(0, 3));
  const [scanCompetitor, setScanCompetitor] = useState<number | null>(null);
  const [scanId, setScanId] = useState<number | null>(presetScan);
  const [sections, setSections] = useState<string[]>(DEFAULT_SECTIONS);
  const [topN, setTopN] = useState(10);
  const [title, setTitle] = useState("");
  const [clientName, setClientName] = useState("");
  const [useAi, setUseAi] = useState(false);
  const [ownOnly, setOwnOnly] = useState(true);
  const [pdf, setPdf] = useState(true);
  const [preview, setPreview] = useState<Report | null>(null);

  const scannable = useMemo(() => (competitors.data ?? []).filter((c) => c.ad_count > 0), [competitors.data]);
  const aiReady = !!settings.data?.integrations.ai.configured;
  const presetScanQ = useQuery({ queryKey: ["scan", presetScan], queryFn: () => api.scan(presetScan!), enabled: !!presetScan });
  useEffect(() => {
    if (presetScanQ.data) setScanCompetitor(presetScanQ.data.competitor_id);
  }, [presetScanQ.data]);
  // Default to the first client when none was preset (or fall back to competitors when there are no clients).
  useEffect(() => {
    if (scope !== "client" || clientId !== null || !clients.data) return;
    const first = clients.data.find((c) => c.competitor_ids.length > 0);
    if (first) setClientId(first.id);
    else if (!presetClient) setScope("competitors");
  }, [clients.data, scope, clientId, presetClient]);

  const scans = useQuery({
    queryKey: ["scans", "for-competitor", scanCompetitor],
    queryFn: () => api.scans({ competitor_id: scanCompetitor!, limit: 30 }),
    enabled: !!scanCompetitor,
  });
  const usableScans = useMemo(() => (scans.data?.items ?? []).filter((s) => s.ads_found > 0), [scans.data]);
  useEffect(() => {
    if (scanCompetitor && usableScans.length && !usableScans.some((s) => s.id === scanId)) setScanId(usableScans[0].id);
  }, [scanCompetitor, usableScans, scanId]);

  const client = clients.data?.find((c) => c.id === clientId);
  const kind: ReportKind = scope === "client" ? "client" : scope === "scan" ? "scan" : picked.length > 1 ? "compare" : "competitor";
  const scopeReady = scope === "client" ? !!client && client.competitor_ids.length > 0 : scope === "scan" ? !!scanId : picked.length > 0;
  const names = (scope === "client" ? client?.competitor_ids ?? [] : scope === "scan" ? (scanCompetitor ? [scanCompetitor] : []) : picked)
    .map((id) => competitors.data?.find((c) => c.id === id)?.name)
    .filter(Boolean) as string[];
  const autoTitle = scope === "client" && client ? `${client.name}: competitor landscape` : names.length ? names.join(" vs ") : "Report title";

  const generate = useMutation({
    mutationFn: () =>
      api.createReport({
        kind,
        scan_id: scope === "scan" ? scanId! : undefined,
        competitor_ids: scope === "competitors" ? picked : undefined,
        client_id: scope === "client" ? clientId! : undefined,
        client_name: clientName.trim() || undefined,
        title: title.trim() || undefined,
        sections,
        top_n: topN,
        ai: useAi && aiReady,
        own_only: ownOnly,
        pdf,
      }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["reports"] });
      if (r.status === "failed") {
        toast.error("Report failed", { description: r.error ?? undefined });
        return;
      }
      const aiError = r.options.ai_usage?.error;
      if (aiError) toast.warning("Report ready, without AI opportunities", { description: `AI step failed, so data-derived opportunities were used. ${aiError}` });
      else toast.success("Report ready", { description: r.options.ai_usage?.cost_usd ? `AI cost $${r.options.ai_usage.cost_usd.toFixed(3)}` : undefined });
      setPreview(r);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Report failed"),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteReport(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reports"] }),
  });

  const brand = settings.data?.settings.reports;
  return (
    <>
      <PageHeader title="Reports" description="Branded, client-ready competitor reports: HTML and PDF." />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Build a report</CardTitle>
              <CardDescription>Choose who it covers, who it's for and what goes in.</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-7">
            <Step n={1} title="Scope" done={scopeReady}>
              <div className="mb-3 inline-flex rounded-lg border border-border p-0.5">
                {([
                  ["client", "Client folder", FolderClosed],
                  ["competitors", "Competitors", Columns3],
                  ["scan", "Single scan", ScanSearch],
                ] as const).map(([key, label, Icon]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setScope(key)}
                    className={cn("inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-medium", scope === key ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground")}
                  >
                    <Icon className="size-3.5" /> {label}
                  </button>
                ))}
              </div>
              {competitors.isLoading || clients.isLoading ? (
                <Skeleton className="h-10" />
              ) : !scannable.length ? (
                <p className="text-sm text-muted-foreground">Run a scan first. Competitors appear here.</p>
              ) : scope === "client" ? (
                !clients.data?.length ? (
                  <p className="text-sm text-muted-foreground">
                    No client folders yet. <Link className="text-primary hover:underline" to="/competitors">Create one on the Competitors page</Link> to report on a client's whole market.
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {clients.data.map((c) => (
                      <Chip key={c.id} active={clientId === c.id} disabled={!c.competitor_ids.length} onClick={() => setClientId(c.id)}>
                        <FolderClosed className="size-3.5" /> {c.name} <span className="num text-muted-foreground">{c.competitor_ids.length}</span>
                      </Chip>
                    ))}
                  </div>
                )
              ) : scope === "competitors" ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    {scannable.map((c) => {
                      const on = picked.includes(c.id);
                      return (
                        <Chip
                          key={c.id}
                          active={on}
                          disabled={!on && picked.length >= 3}
                          onClick={() => setPicked(on ? picked.filter((x) => x !== c.id) : [...picked, c.id])}
                        >
                          <CompetitorAvatar name={c.name} src={c.logo_url} className="size-4 rounded" /> {c.name}
                        </Chip>
                      );
                    })}
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">Pick 1 for a competitor report, or 2–3 for a side-by-side comparison.</p>
                </>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {scannable.map((c) => (
                      <Chip key={c.id} active={scanCompetitor === c.id} onClick={() => { setScanCompetitor(c.id); setScanId(null); }}>{c.name}</Chip>
                    ))}
                  </div>
                  {scanCompetitor && (scans.isLoading ? (
                    <Skeleton className="h-10" />
                  ) : !usableScans.length ? (
                    <p className="text-sm text-muted-foreground">No scans with ads for this competitor.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {usableScans.slice(0, 5).map((s) => (
                        <label key={s.id} className={cn("flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm", scanId === s.id ? "border-primary/60 bg-primary/10" : "border-border hover:bg-accent/40")}>
                          <input type="radio" className="accent-[var(--primary)]" checked={scanId === s.id} onChange={() => setScanId(s.id)} />
                          <span className="font-medium">#{s.id}</span>
                          <span className="truncate text-muted-foreground">{s.query} · {s.country}</span>
                          <span className="num ml-auto shrink-0 text-xs">{s.ads_found} ads · {formatDate(s.started_at)}</span>
                        </label>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </Step>

            <Step
              n={2}
              title="Title & client"
              done={scopeReady}
              aside={
                <Link to="/settings" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                  <Palette className="size-3.5" /> Branding
                </Link>
              }
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="r-title">Title</Label>
                  <Input id="r-title" className="mt-1.5" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} placeholder={autoTitle} />
                </div>
                <div>
                  <Label htmlFor="r-client">Prepared for</Label>
                  <Input id="r-client" className="mt-1.5" value={clientName} maxLength={80} onChange={(e) => setClientName(e.target.value)} placeholder={scope === "client" && client ? client.name : "Client name (optional)"} />
                </div>
              </div>
              {brand && (
                <div className="mt-3 flex items-center gap-3 rounded-lg border border-border px-3 py-2 text-xs text-muted-foreground">
                  {settings.data?.logo_url ? <img src={settings.data.logo_url} alt="" className="h-6 max-w-20 object-contain" /> : <Palette className="size-4" />}
                  <span className="min-w-0 flex-1 truncate">Branded as <span className="font-medium text-foreground">{brand.agency_name}</span></span>
                  <span className="size-4 rounded-full border border-border" style={{ background: brand.primary_color }} title={`Primary ${brand.primary_color}`} />
                  <span className="size-4 rounded-full border border-border" style={{ background: brand.accent_color }} title={`Accent ${brand.accent_color}`} />
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
                      onCheckedChange={(v) => setSections(v === true ? [...sections, s.key] : sections.filter((x) => x !== s.key))}
                    />
                    <span>
                      <span className="block text-sm font-medium">{s.label}</span>
                      <span className="block text-xs text-muted-foreground">{s.hint}</span>
                    </span>
                  </label>
                ))}
              </div>
              {sections.includes("winners") && (
                <div className="mt-4">
                  <div className="mb-2 flex justify-between text-xs">
                    <span className="font-medium">Top winners to feature</span>
                    <span className="num text-muted-foreground">{topN}</span>
                  </div>
                  <Slider min={4} max={30} step={2} value={[topN]} onValueChange={([v]) => setTopN(v)} />
                </div>
              )}
            </Step>

            <Step n={4} title="Options" done>
              <div className="space-y-2">
                <label className={cn("flex items-center justify-between gap-3 rounded-lg border border-border p-3", !aiReady && "opacity-70")}>
                  <span>
                    <span className="flex items-center gap-1.5 text-sm"><Bot className="size-4 text-primary" /> AI-written summary & opportunities</span>
                    <span className="block text-xs text-muted-foreground">
                      {aiReady ? `${settings.data?.integrations.ai.model} · typically under $0.05 per report` : "Set ANTHROPIC_API_KEY in .env to enable. Without it, opportunities are derived from the data."}
                    </span>
                  </span>
                  <Switch checked={useAi && aiReady} disabled={!aiReady} onCheckedChange={setUseAi} />
                </label>
                <label className="flex items-center justify-between gap-3 rounded-lg border border-border p-3">
                  <span>
                    <span className="block text-sm">Brand's own ads only</span>
                    <span className="block text-xs text-muted-foreground">Leave out other advertisers that keyword scans pick up</span>
                  </span>
                  <Switch checked={ownOnly} onCheckedChange={setOwnOnly} />
                </label>
                <label className="flex items-center justify-between gap-3 rounded-lg border border-border p-3">
                  <span className="text-sm">Also export PDF <span className="text-xs text-muted-foreground">(headless Chrome, ~5s)</span></span>
                  <Switch checked={pdf} onCheckedChange={setPdf} />
                </label>
              </div>
              <Button size="lg" className="mt-4 w-full" disabled={!scopeReady || !sections.length || generate.isPending} onClick={() => generate.mutate()}>
                {generate.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}
                {generate.isPending ? (useAi && aiReady ? "Writing with AI and rendering…" : "Rendering report…") : `Generate ${KIND_LABEL[kind].toLowerCase()} report`}
              </Button>
            </Step>
          </CardContent>
        </Card>

        <Card className="xl:self-start">
          <CardHeader>
            <div>
              <CardTitle>Report history</CardTitle>
              <CardDescription>Preview in the app or download.</CardDescription>
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
                      {r.kind === "client" ? <FolderClosed className="size-5" /> : r.kind === "compare" ? <Columns3 className="size-5" /> : <FileText className="size-5" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{r.title}</div>
                      <div className="flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
                        <span>{KIND_LABEL[r.kind] ?? r.kind}</span>
                        {r.options.client_name && <span className="inline-flex items-center gap-0.5">· <User className="size-3" />{r.options.client_name}</span>}
                        <span>· {timeAgo(r.created_at)}</span>
                        {r.options.opportunities_source === "ai" && <Badge variant="outline" className="ml-1"><Bot /> AI</Badge>}
                        {r.options.ai_usage?.error && <Badge variant="warning" className="ml-1" title={r.options.ai_usage.error}><AlertTriangle /> AI skipped</Badge>}
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
              <DialogDescription className="mt-0 text-xs">Preview · the PDF uses the same layout, one section per A4 page</DialogDescription>
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
          {preview?.html_url && <iframe title="Report preview" src={preview.html_url} className="w-full flex-1 rounded-b-2xl bg-[#E7E7EE]" />}
        </DialogContent>
      </Dialog>
    </>
  );
}
