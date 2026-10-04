import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, Circle, Folder, Gauge, Loader2, Palette, Save, ScanSearch } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ErrorState, PageHeader } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { api, type SettingsPayload } from "@/lib/api";
import { cn } from "@/lib/utils";

type S = SettingsPayload["settings"];

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-6 border-b border-border py-3.5 last:border-0">
      <div>
        <div className="text-sm font-medium">{label}</div>
        {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function NumberInput({ value, onChange, min, max, step = 1, suffix }: { value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number; suffix?: string }) {
  return (
    <div className="flex items-center gap-2">
      <Input type="number" className="num h-8 w-24 text-right" value={value} min={min} max={max} step={step} onChange={(e) => onChange(Number(e.target.value))} />
      {suffix && <span className="text-xs text-muted-foreground">{suffix}</span>}
    </div>
  );
}

const WEIGHT_LABELS: Record<string, string> = { longevity: "Longevity", variations: "Variations", platforms: "Placements", recency: "Still active" };

export default function Settings() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const [draft, setDraft] = useState<S | null>(null);
  useEffect(() => {
    if (q.data && !draft) setDraft(structuredClone(q.data.settings));
  }, [q.data, draft]);

  const save = useMutation({
    mutationFn: (patch: Record<string, Record<string, unknown>>) => api.updateSettings(patch),
    onSuccess: (res) => {
      qc.setQueryData(["settings"], res);
      setDraft(structuredClone(res.settings));
      toast.success("Settings saved", { description: res.rescored ? `Re-scored ${res.rescored} ads with the new weights` : undefined });
      if (res.rescored) qc.invalidateQueries();
    },
    onError: (e) => toast.error("Couldn't save", { description: e instanceof Error ? e.message : undefined }),
  });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!draft || !q.data) return <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-48" />)}</div>;

  const sc = draft.scraping;
  const setScraping = (k: string, v: unknown) => setDraft({ ...draft, scraping: { ...sc, [k]: v } as S["scraping"] });
  const weights = draft.scoring.weights;
  const weightSum = Object.values(weights).reduce((a, b) => a + Number(b), 0);
  const integ = q.data.integrations;

  return (
    <>
      <PageHeader title="Settings" description="Tune scraping, scoring and branding. Saved to data/settings.override.yaml." />
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle className="flex items-center gap-2"><ScanSearch className="size-4 text-primary" /> Scraping</CardTitle>
              <CardDescription>How Chrome browses the Ad Library.</CardDescription>
            </div>
            <Button size="sm" disabled={save.isPending} onClick={() => save.mutate({ scraping: draft.scraping })}>
              {save.isPending ? <Loader2 className="animate-spin" /> : <Save />} Save
            </Button>
          </CardHeader>
          <CardContent>
            <Row label="Headless browser" hint="Off = a visible Chrome window opens (debugging)">
              <Switch checked={!!sc.headless} onCheckedChange={(v) => setScraping("headless", v)} />
            </Row>
            <Row label="Driver" hint={q.data.undetected_available ? "Undetected driver is installed" : "Install undetected-chromedriver to enable the alternative driver"}>
              <div className="flex rounded-lg border border-border p-0.5">
                {["chrome", "undetected"].map((d) => (
                  <button
                    key={d}
                    type="button"
                    disabled={d === "undetected" && !q.data.undetected_available}
                    onClick={() => setScraping("driver", d)}
                    className={cn("h-7 rounded-md px-3 text-xs font-medium capitalize disabled:opacity-40", sc.driver === d ? "bg-accent text-foreground" : "text-muted-foreground")}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </Row>
            <Row label="Delay between scrolls" hint={`${sc.delay_range[0]}–${sc.delay_range[1]} seconds, randomized`}>
              <Slider className="w-44" min={0.5} max={8} step={0.1} value={sc.delay_range} onValueChange={(v) => setScraping("delay_range", v)} />
            </Row>
            <Row label="Default max ads"><NumberInput value={sc.max_ads} min={10} max={5000} onChange={(v) => setScraping("max_ads", v)} /></Row>
            <Row label="Stop after idle scrolls" hint="Consecutive scrolls with no new ads"><NumberInput value={sc.no_new_ads_attempts} min={2} max={15} onChange={(v) => setScraping("no_new_ads_attempts", v)} /></Row>
            <Row label="Minimum gap between scans" hint="Rate limit across all scans"><NumberInput value={sc.min_seconds_between_scans} min={0} max={3600} suffix="sec" onChange={(v) => setScraping("min_seconds_between_scans", v)} /></Row>
            <Row label="Card screenshots"><Switch checked={!!sc.screenshots} onCheckedChange={(v) => setScraping("screenshots", v)} /></Row>
            <Row label="Download images"><Switch checked={!!sc.download_media} onCheckedChange={(v) => setScraping("download_media", v)} /></Row>
            <Row label="Download videos" hint="Can use a lot of disk space"><Switch checked={!!sc.download_videos} onCheckedChange={(v) => setScraping("download_videos", v)} /></Row>
            <Row label="Media files per ad"><NumberInput value={sc.max_media_per_ad} min={0} max={20} onChange={(v) => setScraping("max_media_per_ad", v)} /></Row>
            <Row label="Max file size"><NumberInput value={sc.max_media_mb} min={1} max={500} suffix="MB" onChange={(v) => setScraping("max_media_mb", v)} /></Row>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div>
                <CardTitle className="flex items-center gap-2"><Gauge className="size-4 text-primary" /> Winner Score</CardTitle>
                <CardDescription>Weights must add up to 1.0. Saving re-scores every ad.</CardDescription>
              </div>
              <Button size="sm" disabled={save.isPending || Math.abs(weightSum - 1) > 0.01} onClick={() => save.mutate({ scoring: { weights, thresholds: draft.scoring.thresholds } })}>
                <Save /> Save
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {Object.entries(weights).map(([k, v]) => (
                <div key={k}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="font-medium">{WEIGHT_LABELS[k] ?? k}</span>
                    <span className="num text-muted-foreground">{Number(v).toFixed(2)}</span>
                  </div>
                  <Slider min={0} max={1} step={0.05} value={[Number(v)]} onValueChange={([nv]) => setDraft({ ...draft, scoring: { ...draft.scoring, weights: { ...weights, [k]: Math.round(nv * 100) / 100 } } })} />
                </div>
              ))}
              <div className={cn("num text-xs", Math.abs(weightSum - 1) > 0.01 ? "text-destructive" : "text-muted-foreground")}>Sum: {weightSum.toFixed(2)}</div>
              <div className="grid grid-cols-2 gap-3 border-t border-border pt-4">
                <div>
                  <Label>🏆 Winner at ≥</Label>
                  <Input type="number" className="num mt-1.5 h-8" value={draft.scoring.thresholds.winner} onChange={(e) => setDraft({ ...draft, scoring: { ...draft.scoring, thresholds: { ...draft.scoring.thresholds, winner: Number(e.target.value) } } })} />
                </div>
                <div>
                  <Label>📈 Promising at ≥</Label>
                  <Input type="number" className="num mt-1.5 h-8" value={draft.scoring.thresholds.promising} onChange={(e) => setDraft({ ...draft, scoring: { ...draft.scoring, thresholds: { ...draft.scoring.thresholds, promising: Number(e.target.value) } } })} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle className="flex items-center gap-2"><Palette className="size-4 text-primary" /> Report branding</CardTitle>
                <CardDescription>Shown on generated reports.</CardDescription>
              </div>
              <Button size="sm" disabled={save.isPending} onClick={() => save.mutate({ reports: draft.reports })}><Save /> Save</Button>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-3">
                <Label>Agency name</Label>
                <Input className="mt-1.5" value={draft.reports.agency_name} onChange={(e) => setDraft({ ...draft, reports: { ...draft.reports, agency_name: e.target.value } })} />
              </div>
              {(["primary_color", "accent_color"] as const).map((k) => (
                <div key={k}>
                  <Label>{k === "primary_color" ? "Primary" : "Accent"}</Label>
                  <div className="mt-1.5 flex items-center gap-2">
                    <input type="color" value={draft.reports[k]} onChange={(e) => setDraft({ ...draft, reports: { ...draft.reports, [k]: e.target.value } })} className="size-8 cursor-pointer rounded-md border border-border bg-transparent" />
                    <span className="num text-xs text-muted-foreground">{draft.reports[k]}</span>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle className="flex items-center gap-2"><Bot className="size-4 text-primary" /> Integrations</CardTitle>
                <CardDescription>Configured through the .env file (secrets never leave your machine).</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              {[
                ["AI copy analysis", integ.ai.configured, integ.ai.configured ? `Model: ${integ.ai.model}` : "Set ANTHROPIC_API_KEY"],
                ["Telegram alerts", integ.telegram.configured, "TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID"],
                ["Email alerts", integ.email.configured, "SMTP_HOST, SMTP_TO, …"],
              ].map(([label, ok, hint]) => (
                <div key={label as string} className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2.5">
                  <div>
                    <div className="text-sm font-medium">{label}</div>
                    <div className="text-xs text-muted-foreground">{hint}</div>
                  </div>
                  {ok ? <Badge variant="success"><CheckCircle2 /> Connected</Badge> : <Badge variant="muted"><Circle /> Not configured</Badge>}
                </div>
              ))}
              <div className="flex items-center gap-2 pt-2 text-xs text-muted-foreground">
                <Folder className="size-3.5" /> Data folder: <span className="num truncate">{q.data.data_dir}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
