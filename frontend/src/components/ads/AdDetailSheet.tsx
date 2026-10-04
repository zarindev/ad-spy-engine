import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays, Camera, Check, Copy, ExternalLink, Globe, Hash, Layers, Link2, Loader2, MonitorSmartphone, MousePointerClick, Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import { AiAnalyzeButton } from "@/components/ai/AiAnalyzeButton";
import { AnalysisCards } from "@/components/ai/AnalysisCards";
import { SaveToBoard } from "@/components/boards/SaveToBoard";
import { toast } from "sonner";
import { ErrorState } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type AdDetail } from "@/lib/api";
import { copyText, formatDate, titleCase } from "@/lib/utils";
import { PlatformIcons } from "./PlatformIcons";
import { BADGE_META, ScoreBadge, ScoreRing } from "./ScoreBadge";

function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-7 px-2 text-xs"
      onClick={async () => {
        if (await copyText(text)) {
          setDone(true);
          toast.success(`${label} copied`);
          setTimeout(() => setDone(false), 1500);
        }
      }}
    >
      {done ? <Check /> : <Copy />} Copy
    </Button>
  );
}

function TextBlock({ label, text }: { label: string; text: string | null }) {
  if (!text) return null;
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</span>
        <CopyButton text={text} label={label} />
      </div>
      <p className="text-sm leading-relaxed whitespace-pre-line">{text}</p>
    </div>
  );
}

const COMPONENT_LABELS: Record<string, { label: string; hint: string }> = {
  longevity: { label: "Longevity", hint: "Days running vs. 90 days" },
  variations: { label: "Variations", hint: "log₂(variations + 1) / 4" },
  platforms: { label: "Placements", hint: "Placements vs. 4" },
  recency: { label: "Still active", hint: "1 if running now" },
};

export function ScoreBreakdownPanel({ ad }: { ad: AdDetail }) {
  const b = ad.score_breakdown;
  if (!b?.components) return null;
  const color = BADGE_META[ad.badge].color;
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-4 flex items-center gap-3">
        <ScoreRing score={ad.score} badge={ad.badge} size={56} stroke={5} />
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            Why this score <ScoreBadge badge={ad.badge} />
          </div>
          <p className="text-xs text-muted-foreground">Winner Score is a heuristic from public signals, not performance data.</p>
        </div>
      </div>
      <div className="space-y-3">
        {Object.entries(b.components).map(([key, c]) => (
          <div key={key}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span>
                <span className="font-medium">{COMPONENT_LABELS[key]?.label ?? key}</span>
                <span className="ml-2 text-muted-foreground">{COMPONENT_LABELS[key]?.hint}</span>
              </span>
              <span className="num text-muted-foreground">
                {c.points.toFixed(1)} / {c.max_points.toFixed(0)}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full transition-all" style={{ width: `${(c.points / c.max_points) * 100}%`, background: color }} />
            </div>
          </div>
        ))}
      </div>
      <ul className="mt-4 space-y-1.5 border-t border-border pt-3">
        {b.explanation.map((line) => (
          <li key={line} className="flex gap-2 text-xs text-muted-foreground">
            <Sparkles className="mt-0.5 size-3 shrink-0 text-primary" /> {line}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Fact({ icon: Icon, label, children }: { icon: typeof Hash; label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 rounded-lg bg-muted/50 px-3 py-2.5">
      <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0">
        <div className="text-[11px] text-muted-foreground">{label}</div>
        <div className="text-sm font-medium break-words">{children}</div>
      </div>
    </div>
  );
}

function SectionTitle({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{children}</span>
      {action}
    </div>
  );
}

function VariationGroup({ ad, onOpen }: { ad: AdDetail; onOpen: (id: number) => void }) {
  if (!ad.group || ad.group.size < 2) return null;
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <SectionTitle>Variation group</SectionTitle>
      <div className="mb-3">
        <div className="text-lg font-semibold">{ad.group.label}</div>
        <div className="text-xs text-muted-foreground">{ad.group.size} ads share this creative or near-identical copy</div>
      </div>
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
        {ad.group.members.map((m) => (
          <button key={m.id} type="button" onClick={() => onOpen(m.id)} className="group relative aspect-square overflow-hidden rounded-lg border border-border bg-muted" title={m.headline ?? m.ad_copy ?? ""}>
            {(m.thumbnail_url || m.screenshot_url) && <img src={(m.thumbnail_url ?? m.screenshot_url)!} alt="" loading="lazy" className="size-full object-cover transition-transform group-hover:scale-105" />}
            <span className="num absolute right-1 bottom-1 rounded bg-black/70 px-1 text-[10px] text-white">{m.score}</span>
          </button>
        ))}
      </div>
      {ad.group.size - 1 > ad.group.members.length && (
        <p className="mt-2 text-xs text-muted-foreground">+{ad.group.size - 1 - ad.group.members.length} more in this group</p>
      )}
    </div>
  );
}

function LandingSection({ ad }: { ad: AdDetail }) {
  const qc = useQueryClient();
  const capture = useMutation({
    mutationFn: () => api.captureLanding(ad.id),
    onSuccess: () => {
      toast.success("Landing page captured");
      qc.invalidateQueries({ queryKey: ["ad", ad.id] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Capture failed"),
  });
  if (!ad.landing_url) return null;
  const lp = ad.landing_page;
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <SectionTitle
        action={
          ad.landing_capturable && (
            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" disabled={capture.isPending} onClick={() => capture.mutate()}>
              {capture.isPending ? <Loader2 className="animate-spin" /> : <Camera />} {lp ? "Recapture" : "Capture"}
            </Button>
          )
        }
      >
        Landing page
      </SectionTitle>
      {lp?.status === "ok" && lp.screenshot_url ? (
        <a href={lp.final_url ?? lp.url} target="_blank" rel="noreferrer" className="group block">
          <div className="overflow-hidden rounded-lg border border-border">
            <div className="flex items-center gap-1.5 border-b border-border bg-muted px-2.5 py-1.5">
              <span className="size-2 rounded-full bg-destructive/60" /><span className="size-2 rounded-full bg-warning/60" /><span className="size-2 rounded-full bg-success/60" />
              <span className="num ml-2 truncate text-[10px] text-muted-foreground">{(lp.final_url ?? lp.url).replace(/^https?:\/\//, "")}</span>
            </div>
            <img src={lp.screenshot_url} alt="Landing page" className="w-full transition-opacity group-hover:opacity-90" />
          </div>
          {lp.title && <div className="mt-2 truncate text-sm font-medium">{lp.title}</div>}
          <div className="text-[11px] text-muted-foreground">Captured {formatDate(lp.captured_at)}</div>
        </a>
      ) : (
        <div className="flex items-center gap-3 rounded-lg bg-muted/50 px-3 py-3 text-sm text-muted-foreground">
          <Globe className="size-4 shrink-0" />
          {lp?.status === "failed"
            ? `Capture failed: ${lp.error ?? "unknown error"}`
            : ad.landing_capturable
              ? "Not captured yet — landing pages of top ads are captured after each scan."
              : "This ad points to an on-platform destination (Facebook, Instagram, app store), so there's no page to capture."}
        </div>
      )}
    </div>
  );
}

function AiSection({ ad }: { ad: AdDetail }) {
  if (ad.analysis) return <AnalysisCards analysis={ad.analysis} />;
  if (!ad.ad_copy && !ad.headline) return null;
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-primary/40 bg-primary/5 p-4">
      <div>
        <div className="text-sm font-medium">AI copy analysis</div>
        <div className="text-xs text-muted-foreground">Hook type, angle, emotion, offer and one idea worth stealing.</div>
      </div>
      <AiAnalyzeButton scope={{ ad_ids: [ad.id] }} label="Analyze" size="sm" />
    </div>
  );
}

function DetailBody({ ad, onOpen }: { ad: AdDetail; onOpen: (id: number) => void }) {
  const visuals = [
    ad.thumbnail_url && { key: "creative", label: "Creative", src: ad.thumbnail_url },
    ad.screenshot_url && { key: "card", label: "Library card", src: ad.screenshot_url },
    ...ad.media_files.filter((f) => !f.endsWith(".mp4")).slice(0, 3).map((src, i) => ({ key: `m${i}`, label: `#${i + 1}`, src })),
  ].filter(Boolean) as { key: string; label: string; src: string }[];
  const videos = ad.media_files.filter((f) => f.endsWith(".mp4"));

  return (
    <div className="grid gap-6 p-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <div className="space-y-3">
        {videos.length > 0 && <video src={videos[0]} controls className="w-full rounded-xl border border-border bg-black" />}
        {visuals.length > 0 ? (
          <Tabs defaultValue={visuals[0].key}>
            <TabsList className="mb-3 h-auto flex-wrap">
              {visuals.map((v) => (
                <TabsTrigger key={v.key} value={v.key}>
                  {v.label}
                </TabsTrigger>
              ))}
            </TabsList>
            {visuals.map((v) => (
              <TabsContent key={v.key} value={v.key}>
                <a href={v.src} target="_blank" rel="noreferrer">
                  <img src={v.src} alt={v.label} className="w-full rounded-xl border border-border bg-white object-contain" />
                </a>
              </TabsContent>
            ))}
          </Tabs>
        ) : (
          <div className="grid aspect-square place-items-center rounded-xl border border-dashed border-border text-sm text-muted-foreground">
            No visuals captured
          </div>
        )}
        <LandingSection ad={ad} />
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-2">
          <Fact icon={CalendarDays} label="Started running">
            {formatDate(ad.start_date)} <span className="text-muted-foreground">· {ad.days_running} days</span>
          </Fact>
          <Fact icon={Hash} label="Status">
            <Badge variant={ad.status === "active" ? "success" : "muted"}>{titleCase(ad.status)}</Badge>
          </Fact>
          <Fact icon={MonitorSmartphone} label="Placements">
            <PlatformIcons platforms={ad.platforms} size="size-4" />
          </Fact>
          <Fact icon={Layers} label="Format · variations">
            {titleCase(ad.media_type)} · ×{ad.variation_count}
          </Fact>
          <Fact icon={MousePointerClick} label="Call to action">
            {ad.cta_text ?? "—"}
          </Fact>
          <Fact icon={Link2} label="Landing page">
            {ad.landing_url ? (
              <a href={ad.landing_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                {ad.landing_url.replace(/^https?:\/\/(www\.)?/, "")}
              </a>
            ) : (
              "—"
            )}
          </Fact>
        </div>

        <AiSection ad={ad} />
        <TextBlock label="Ad copy" text={ad.ad_copy} />
        <TextBlock label="Headline" text={ad.headline} />
        <TextBlock label="Description" text={ad.description} />
        <ScoreBreakdownPanel ad={ad} />
        <VariationGroup ad={ad} onOpen={onOpen} />

        {ad.history.length > 1 && (
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">Seen in {ad.history.length} scans</div>
            <div className="space-y-1">
              {ad.history.map((h) => (
                <div key={h.scan_id} className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Scan #{h.scan_id} · {formatDate(h.captured_at)}</span>
                  <span className="num">
                    {h.days_running}d · ×{h.variation_count} · {h.score}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function AdDetailSheet({ adId, onClose }: { adId: number | null; onClose: () => void }) {
  const [current, setCurrent] = useState<number | null>(adId);
  useEffect(() => setCurrent(adId), [adId]);
  const query = useQuery({ queryKey: ["ad", current], queryFn: () => api.ad(current!), enabled: current !== null });
  const ad = query.data;
  return (
    <Sheet open={current !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent>
        <div className="flex items-center gap-3 border-b border-border px-6 py-4 pr-14">
          {ad?.page_profile_image && <img src={ad.page_profile_image} alt="" className="size-9 rounded-lg border border-border" onError={(e) => (e.currentTarget.style.display = "none")} />}
          <div className="min-w-0 flex-1">
            <SheetTitle className="truncate text-base font-semibold">{ad?.page_name ?? "Loading ad…"}</SheetTitle>
            <SheetDescription className="num text-xs text-muted-foreground">Library ID {ad?.library_id ?? "…"}</SheetDescription>
          </div>
          {ad && (
            <div className="flex gap-2">
              <CopyButton text={ad.library_id} label="Library ID" />
              <SaveToBoard adIds={[ad.id]} />
              <Button variant="outline" size="sm" asChild>
                <a href={ad.library_url} target="_blank" rel="noreferrer">
                  <ExternalLink /> Ad Library
                </a>
              </Button>
            </div>
          )}
        </div>
        <div className="flex-1 overflow-y-auto">
          {query.isLoading && (
            <div className="grid gap-6 p-6 lg:grid-cols-2">
              <Skeleton className="aspect-square" />
              <div className="space-y-3">
                <Skeleton className="h-16" />
                <Skeleton className="h-32" />
                <Skeleton className="h-48" />
              </div>
            </div>
          )}
          {query.isError && <ErrorState className="m-6" error={query.error} onRetry={() => query.refetch()} />}
          {ad && <DetailBody ad={ad} onOpen={setCurrent} />}
        </div>
      </SheetContent>
    </Sheet>
  );
}
