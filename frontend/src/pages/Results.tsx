import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { ArrowDownWideNarrow, Copy, Download, FilterX, Layers, LayoutGrid, List, Loader2, Search, SearchX, X } from "lucide-react";
import { AiAnalyzeButton } from "@/components/ai/AiAnalyzeButton";
import { Switch } from "@/components/ui/switch";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { AdCard, AdCardSkeleton, AdRow } from "@/components/ads/AdCard";
import { AdDetailSheet } from "@/components/ads/AdDetailSheet";
import { ALL_PLATFORMS, PlatformIcon } from "@/components/ads/PlatformIcons";
import { BADGE_META } from "@/components/ads/ScoreBadge";
import { EmptyState, ErrorState, PageHeader } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import { api, exportUrl, type Ad, type AdQuery, type Badge } from "@/lib/api";
import { cn, copyText, formatNumber, titleCase } from "@/lib/utils";

const PAGE = 48;
const SORTS = [
  { value: "score", label: "Winner Score" },
  { value: "days", label: "Days running" },
  { value: "newest", label: "Newest start date" },
  { value: "variations", label: "Most variations" },
  { value: "first_seen", label: "Recently discovered" },
] as const;
const FORMATS = ["image", "video", "carousel", "dynamic", "catalog", "text"];

function FilterMenu({ label, value, options, onChange }: { label: string; value: string; options: { value: string; label: React.ReactNode }[]; onChange: (v: string) => void }) {
  const current = options.find((o) => o.value === value);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-xs font-medium transition-colors",
            value ? "border-primary/50 bg-primary/10 text-foreground" : "border-border text-muted-foreground hover:text-foreground",
          )}
        >
          {label}
          {value && <span className="text-foreground">: {current?.label}</span>}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuItem onSelect={() => onChange("")}>Any {label.toLowerCase()}</DropdownMenuItem>
        <DropdownMenuSeparator />
        {options.map((o) => (
          <DropdownMenuItem key={o.value} onSelect={() => onChange(o.value)} className={cn(o.value === value && "bg-accent")}>
            {o.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default function Results() {
  const [params, setParams] = useSearchParams();
  const [view, setView] = useLocalStorage<"grid" | "list">("adspy-results-view", "grid");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [openAd, setOpenAd] = useState<number | null>(params.get("ad") ? Number(params.get("ad")) : null);
  const [search, setSearch] = useState(params.get("q") ?? "");

  const query: AdQuery = {
    scan_id: params.get("scan") ? Number(params.get("scan")) : undefined,
    competitor_id: params.get("competitor") ? Number(params.get("competitor")) : undefined,
    q: params.get("q") ?? undefined,
    badge: (params.get("badge") as Badge) ?? undefined,
    media_type: params.get("media") ?? undefined,
    platform: params.get("platform") ?? undefined,
    status: params.get("status") ?? undefined,
    sort: (params.get("sort") as AdQuery["sort"]) ?? "score",
    group_key: params.get("group") ?? undefined,
    grouped: params.get("grouped") === "1" || undefined,
  };
  const update = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    Object.entries(patch).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next, { replace: true });
    setSelected(new Set());
  };

  useEffect(() => {
    const t = setTimeout(() => {
      if ((params.get("q") ?? "") !== search) update({ q: search || null });
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const competitors = useQuery({ queryKey: ["competitors"], queryFn: api.competitors });
  const scan = useQuery({ queryKey: ["scan", query.scan_id], queryFn: () => api.scan(query.scan_id!), enabled: !!query.scan_id });

  const ads = useInfiniteQuery({
    queryKey: ["ads", query],
    queryFn: ({ pageParam }) => api.ads({ ...query, limit: PAGE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, p) => n + p.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
  });
  const items: Ad[] = useMemo(() => ads.data?.pages.flatMap((p) => p.items) ?? [], [ads.data]);
  const total = ads.data?.pages[0]?.total ?? 0;

  const sentinel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && ads.hasNextPage && !ads.isFetchingNextPage) ads.fetchNextPage();
    }, { rootMargin: "600px" });
    io.observe(el);
    return () => io.disconnect();
  }, [ads]);

  const onSelect = (ad: Ad, on: boolean) =>
    setSelected((s) => {
      const n = new Set(s);
      if (on) n.add(ad.id);
      else n.delete(ad.id);
      return n;
    });
  const openDetail = (ad: Ad) => setOpenAd(ad.id);
  const filtersActive = ["q", "badge", "media", "platform", "status", "competitor", "scan", "group"].some((k) => params.get(k));
  const compName = competitors.data?.find((c) => c.id === query.competitor_id)?.name;

  return (
    <>
      <PageHeader
        title="Results gallery"
        description={
          <>
            {formatNumber(total)} {query.grouped ? "variation groups" : "ads"}
            {scan.data && (
              <>
                {" "}from scan <Link to={`/scans/${scan.data.id}`} className="text-primary hover:underline">#{scan.data.id} “{scan.data.query}”</Link>
              </>
            )}
            {compName && !scan.data && <> from {compName}</>}
          </>
        }
        actions={
          <Button variant="outline" asChild>
            <a href={exportUrl.adsCsv(query)}>
              <Download /> Export CSV
            </a>
          </Button>
        }
      />

      <Card className="mb-5 flex flex-wrap items-center gap-2 p-3">
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search copy, headlines, pages, Library ID…" className="pl-9" />
        </div>
        {query.group_key && (
          <button type="button" onClick={() => update({ group: null })} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-primary/50 bg-primary/10 px-3 text-xs font-medium">
            One variation group <X className="size-3" />
          </button>
        )}
        {query.scan_id && (
          <button type="button" onClick={() => update({ scan: null })} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-primary/50 bg-primary/10 px-3 text-xs font-medium">
            Scan #{query.scan_id} <X className="size-3" />
          </button>
        )}
        <FilterMenu
          label="Competitor"
          value={params.get("competitor") ?? ""}
          options={(competitors.data ?? []).map((c) => ({ value: String(c.id), label: c.name }))}
          onChange={(v) => update({ competitor: v || null })}
        />
        <FilterMenu
          label="Badge"
          value={params.get("badge") ?? ""}
          options={(Object.keys(BADGE_META) as Badge[]).map((b) => {
            const Icon = BADGE_META[b].icon;
            return { value: b, label: <span className="inline-flex items-center gap-1.5"><Icon className="size-3.5" style={{ color: BADGE_META[b].color }} />{BADGE_META[b].label}</span> };
          })}
          onChange={(v) => update({ badge: v || null })}
        />
        <FilterMenu label="Format" value={params.get("media") ?? ""} options={FORMATS.map((f) => ({ value: f, label: titleCase(f) }))} onChange={(v) => update({ media: v || null })} />
        <FilterMenu
          label="Platform"
          value={params.get("platform") ?? ""}
          options={ALL_PLATFORMS.map((p) => ({ value: p, label: <span className="inline-flex items-center gap-1.5"><PlatformIcon platform={p} />{titleCase(p)}</span> }))}
          onChange={(v) => update({ platform: v || null })}
        />
        <FilterMenu label="Status" value={params.get("status") ?? ""} options={[{ value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }]} onChange={(v) => update({ status: v || null })} />
        {filtersActive && (
          <Button variant="ghost" size="sm" onClick={() => { setSearch(""); setParams(new URLSearchParams(), { replace: true }); }}>
            <FilterX /> Clear
          </Button>
        )}
        <div className="ml-auto flex items-center gap-2">
          <label className="flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-border px-3 text-xs font-medium text-muted-foreground" title="Show one ad per variation group">
            <Layers className="size-3.5" /> Collapse variations
            <Switch checked={!!query.grouped} onCheckedChange={(v) => update({ grouped: v ? "1" : null })} />
          </label>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-9">
                <ArrowDownWideNarrow /> {SORTS.find((s) => s.value === query.sort)?.label}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuLabel>Sort by</DropdownMenuLabel>
              {SORTS.map((s) => (
                <DropdownMenuItem key={s.value} onSelect={() => update({ sort: s.value === "score" ? null : s.value })}>
                  {s.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <div className="flex rounded-lg border border-border p-0.5">
            {(["grid", "list"] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-label={`${v} view`}
                onClick={() => setView(v)}
                className={cn("grid size-8 place-items-center rounded-md text-muted-foreground", view === v && "bg-accent text-foreground")}
              >
                {v === "grid" ? <LayoutGrid className="size-4" /> : <List className="size-4" />}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {selected.size > 0 && (
        <div className="glass sticky top-20 z-20 mb-4 flex items-center gap-3 rounded-xl border border-primary/40 px-4 py-2.5 shadow-lg">
          <span className="text-sm font-medium">{selected.size} selected</span>
          <Button size="sm" variant="outline" asChild>
            <a href={exportUrl.adsCsv({ ids: [...selected].join(",") })}>
              <Download /> Export selected
            </a>
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={async () => {
              const ids = items.filter((a) => selected.has(a.id)).map((a) => a.library_id).join("\n");
              if (await copyText(ids)) toast.success(`Copied ${selected.size} Library IDs`);
            }}
          >
            <Copy /> Copy Library IDs
          </Button>
          <AiAnalyzeButton size="sm" scope={{ ad_ids: [...selected], limit: 2000 }} label="Analyze selected" />
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set(items.map((a) => a.id)))}>
            Select all loaded
          </Button>
          <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setSelected(new Set())}>
            <X /> Clear
          </Button>
        </div>
      )}

      {ads.isError ? (
        <ErrorState error={ads.error} onRetry={() => ads.refetch()} />
      ) : ads.isLoading ? (
        <div className="columns-1 gap-4 sm:columns-2 xl:columns-3 2xl:columns-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <AdCardSkeleton key={i} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title={filtersActive ? "No ads match these filters" : "No ads yet"}
          description={filtersActive ? "Try removing a filter or searching for something else." : "Run a scan to start building your competitive ad library."}
          action={
            filtersActive ? (
              <Button variant="outline" onClick={() => { setSearch(""); setParams(new URLSearchParams()); }}>
                <FilterX /> Clear filters
              </Button>
            ) : (
              <Button asChild>
                <Link to="/scan/new">Start a scan</Link>
              </Button>
            )
          }
        />
      ) : view === "grid" ? (
        <div className="columns-1 gap-4 sm:columns-2 xl:columns-3 2xl:columns-4">
          {items.map((ad, i) => (
            <AdCard key={ad.id} ad={ad} index={i % PAGE} onOpen={openDetail} selected={selected.has(ad.id)} onSelect={onSelect} />
          ))}
        </div>
      ) : (
        <Card className="overflow-hidden">
          {items.map((ad) => (
            <AdRow key={ad.id} ad={ad} onOpen={openDetail} selected={selected.has(ad.id)} onSelect={onSelect} />
          ))}
        </Card>
      )}
      <div ref={sentinel} className="flex h-16 items-center justify-center">
        {ads.isFetchingNextPage && <Loader2 className="size-5 animate-spin text-muted-foreground" />}
      </div>
      <AdDetailSheet adId={openAd} onClose={() => setOpenAd(null)} />
    </>
  );
}
