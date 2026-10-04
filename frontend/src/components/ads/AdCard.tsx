import { CalendarDays, ImageOff, Layers } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import type { Ad } from "@/lib/api";
import { cn, titleCase } from "@/lib/utils";
import { PlatformIcons } from "./PlatformIcons";
import { ScoreBadge, ScoreRing } from "./ScoreBadge";

function Creative({ ad, className }: { ad: Ad; className?: string }) {
  const sources = [ad.thumbnail_url, ad.screenshot_url].filter(Boolean) as string[];
  const [idx, setIdx] = useState(0);
  if (idx >= sources.length) {
    return (
      <div className={cn("grid aspect-square place-items-center bg-muted text-muted-foreground", className)}>
        <ImageOff className="size-6" />
      </div>
    );
  }
  return (
    <img
      src={sources[idx]}
      alt={ad.headline ?? `Ad ${ad.library_id}`}
      loading="lazy"
      onError={() => setIdx((i) => i + 1)}
      className={cn("block w-full bg-muted object-cover", className)}
    />
  );
}

interface CardProps {
  ad: Ad;
  onOpen: (ad: Ad) => void;
  selected?: boolean;
  onSelect?: (ad: Ad, selected: boolean) => void;
  index?: number;
}

export function AdCard({ ad, onOpen, selected, onSelect, index = 0 }: CardProps) {
  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index, 12) * 0.025 }}
      className={cn(
        "group mb-4 break-inside-avoid overflow-hidden rounded-xl border bg-card transition-all hover:-translate-y-0.5 hover:shadow-[0_12px_40px_-12px_var(--glow)]",
        selected ? "border-primary ring-2 ring-primary/30" : "border-border hover:border-primary/40",
        ad.badge === "winner" && !selected && "border-gold/30",
      )}
    >
      <button type="button" onClick={() => onOpen(ad)} className="relative block w-full text-left">
        <Creative ad={ad} className="max-h-[420px]" />
        <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between bg-gradient-to-b from-black/55 to-transparent p-2.5">
          <ScoreBadge badge={ad.badge} className="backdrop-blur-md" />
          <div className="rounded-full bg-black/50 p-0.5 backdrop-blur-md">
            <ScoreRing score={ad.score} badge={ad.badge} size={38} stroke={3.5} className="text-white" />
          </div>
        </div>
        {ad.group_size > 1 && (
          <span className="absolute right-2 bottom-2 inline-flex items-center gap-1 rounded-full bg-primary/85 px-2 py-0.5 text-[11px] font-medium text-white backdrop-blur-md" title="Ads sharing this creative or copy">
            {ad.group_creatives} creative{ad.group_creatives !== 1 ? "s" : ""} · {ad.group_copies} cop{ad.group_copies !== 1 ? "ies" : "y"}
          </span>
        )}
        {ad.variation_count > 1 && (
          <span className="absolute bottom-2 left-2 inline-flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 text-[11px] font-medium text-white backdrop-blur-md">
            <Layers className="size-3" /> {ad.variation_count} variations
          </span>
        )}
      </button>
      <div className="space-y-2.5 p-3.5">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-semibold">{ad.page_name ?? "Unknown page"}</span>
          {onSelect && (
            <Checkbox
              checked={!!selected}
              onCheckedChange={(v) => onSelect(ad, v === true)}
              aria-label="Select ad"
              className={cn("transition-opacity", selected ? "opacity-100" : "opacity-0 group-hover:opacity-100")}
            />
          )}
        </div>
        {ad.headline && <p className="line-clamp-1 text-[13px] font-medium">{ad.headline}</p>}
        {ad.ad_copy && <p className="line-clamp-3 text-[13px] leading-relaxed text-muted-foreground">{ad.ad_copy}</p>}
        <div className="flex items-center justify-between gap-2 pt-1">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <CalendarDays className="size-3.5" />
              <span className="num">{ad.days_running}d</span>
            </span>
            <span className="rounded-md bg-muted px-1.5 py-0.5 text-[11px]">{titleCase(ad.media_type)}</span>
          </div>
          <PlatformIcons platforms={ad.platforms} />
        </div>
      </div>
    </motion.article>
  );
}

export function AdRow({ ad, onOpen, selected, onSelect }: CardProps) {
  return (
    <div
      className={cn(
        "group flex items-center gap-4 border-b border-border px-4 py-3 transition-colors last:border-0 hover:bg-accent/50",
        selected && "bg-primary/5",
      )}
    >
      {onSelect && <Checkbox checked={!!selected} onCheckedChange={(v) => onSelect(ad, v === true)} aria-label="Select ad" />}
      <button type="button" onClick={() => onOpen(ad)} className="flex min-w-0 flex-1 items-center gap-4 text-left">
        <div className="size-14 shrink-0 overflow-hidden rounded-lg border border-border">
          <Creative ad={ad} className="size-14" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold">{ad.page_name}</span>
            <ScoreBadge badge={ad.badge} />
          </div>
          <p className="mt-0.5 truncate text-[13px] text-muted-foreground">{ad.headline || ad.ad_copy || "—"}</p>
        </div>
      </button>
      <span className="hidden w-20 text-xs text-muted-foreground lg:block">{titleCase(ad.media_type)}</span>
      <span className="num hidden w-14 text-right text-sm md:block">{ad.days_running}d</span>
      <span className="num hidden w-10 text-right text-sm text-muted-foreground md:block" title="Variations">
        ×{ad.variation_count}
      </span>
      <PlatformIcons platforms={ad.platforms} className="hidden w-28 xl:flex" />
      <ScoreRing score={ad.score} badge={ad.badge} size={36} stroke={3} />
    </div>
  );
}

export function AdCardSkeleton() {
  return (
    <div className="mb-4 break-inside-avoid overflow-hidden rounded-xl border border-border bg-card">
      <div className="skeleton aspect-[4/5] rounded-none" />
      <div className="space-y-2 p-3.5">
        <div className="skeleton h-4 w-1/2" />
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-4/5" />
      </div>
    </div>
  );
}

