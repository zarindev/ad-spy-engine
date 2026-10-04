import { useQuery } from "@tanstack/react-query";
import {
  CalendarDays, Check, Copy, ExternalLink, Hash, Layers, Link2, MonitorSmartphone, MousePointerClick, Sparkles,
} from "lucide-react";
import { useState } from "react";
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

function DetailBody({ ad }: { ad: AdDetail }) {
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

        <TextBlock label="Ad copy" text={ad.ad_copy} />
        <TextBlock label="Headline" text={ad.headline} />
        <TextBlock label="Description" text={ad.description} />
        <ScoreBreakdownPanel ad={ad} />

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
  const query = useQuery({ queryKey: ["ad", adId], queryFn: () => api.ad(adId!), enabled: adId !== null });
  const ad = query.data;
  return (
    <Sheet open={adId !== null} onOpenChange={(o) => !o && onClose()}>
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
          {ad && <DetailBody ad={ad} />}
        </div>
      </SheetContent>
    </Sheet>
  );
}
