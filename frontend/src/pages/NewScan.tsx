import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, Clock, ExternalLink, Eye, Globe2, Hash, Info, Loader2, Radar, Search, Type } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { PlatformIcon } from "@/components/ads/PlatformIcons";
import { PageHeader } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { api, type ScanCreate } from "@/lib/api";
import { COUNTRIES, countryName, flag } from "@/lib/countries";
import { cn, estimateScanSeconds, formatDuration } from "@/lib/utils";

const MEDIA = [
  { value: "all", label: "All media" },
  { value: "image", label: "Images" },
  { value: "video", label: "Videos" },
  { value: "carousel", label: "Carousels" },
  { value: "meme", label: "Memes" },
];
const PLATFORMS = [
  { value: "facebook", label: "Facebook" },
  { value: "instagram", label: "Instagram" },
  { value: "messenger", label: "Messenger" },
  { value: "audience_network", label: "Audience Network" },
];
const STATUSES = [
  { value: "active", label: "Active ads" },
  { value: "all", label: "Active + inactive" },
  { value: "inactive", label: "Inactive only" },
] as const;

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-all",
        active ? "border-primary/60 bg-primary/15 text-foreground" : "border-border text-muted-foreground hover:border-primary/30 hover:text-foreground",
      )}
    >
      {active && <Check className="size-3 text-primary" />}
      {children}
    </button>
  );
}

function CountryPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const list = useMemo(
    () => COUNTRIES.filter((c) => `${c.name} ${c.code}`.toLowerCase().includes(q.toLowerCase())),
    [q],
  );
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" className="inline-flex h-8 items-center gap-2 rounded-full border border-border px-3 text-xs font-medium hover:border-primary/40">
          <span>{flag(value)}</span> {countryName(value)} <ChevronDown className="size-3 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0">
        <div className="border-b border-border p-2">
          <Input autoFocus placeholder="Search countries…" value={q} onChange={(e) => setQ(e.target.value)} className="h-8" />
        </div>
        <div className="max-h-72 overflow-y-auto p-1">
          {list.map((c) => (
            <button
              key={c.code}
              type="button"
              onClick={() => {
                onChange(c.code);
                setOpen(false);
                setQ("");
              }}
              className={cn("flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent", c.code === value && "bg-accent")}
            >
              <span>{flag(c.code)}</span>
              <span className="flex-1">{c.name}</span>
              <span className="num text-[11px] text-muted-foreground">{c.code}</span>
            </button>
          ))}
          {!list.length && <div className="p-3 text-center text-xs text-muted-foreground">No country matches</div>}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export default function NewScan() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const stats = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });

  const [form, setForm] = useState<ScanCreate>({
    query: params.get("q") ?? "",
    search_type: params.get("type") === "page_id" ? "page_id" : "keyword",
    competitor_name: "",
    country: "US",
    media_type: "all",
    platforms: [],
    active_status: "active",
    max_ads: 200,
    exact_page: false,
    headless: null,
  });
  const [visible, setVisible] = useState(false);
  const set = <K extends keyof ScanCreate>(k: K, v: ScanCreate[K]) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    const s = settings.data?.settings.scraping;
    if (s) {
      setForm((f) => ({ ...f, max_ads: s.max_ads ?? f.max_ads }));
      setVisible(!s.headless);
    }
  }, [settings.data]);

  const pageIdInvalid = form.search_type === "page_id" && form.query.trim() !== "" && !/^\d+$/.test(form.query.trim());
  const canSubmit = form.query.trim().length > 0 && !pageIdInvalid;
  const eta = estimateScanSeconds(form.max_ads, stats.data?.avg_ads_per_minute);

  const preview = useQuery({
    queryKey: ["preview-url", form.query, form.search_type, form.country, form.media_type, form.platforms.join(",")],
    queryFn: () =>
      api.previewUrl({ query: form.query || "…", search_type: form.search_type, country: form.country, media_type: form.media_type, platforms: form.platforms.join(",") }),
    enabled: form.query.trim().length > 0 && !pageIdInvalid,
    staleTime: 60000,
  });

  const start = useMutation({
    mutationFn: () => api.startScan({ ...form, query: form.query.trim(), headless: !visible, competitor_name: form.competitor_name?.trim() || undefined }),
    onSuccess: (scan) => {
      qc.invalidateQueries({ queryKey: ["active-scans"] });
      toast.success("Scan queued", { description: `Collecting ads for “${scan.query}”` });
      navigate(`/scans/${scan.id}`);
    },
    onError: (e) => toast.error("Couldn't start the scan", { description: e instanceof Error ? e.message : undefined }),
  });

  return (
    <>
      <PageHeader title="New scan" description="Collect every ad a competitor is running in the public Meta Ad Library." />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) start.mutate();
        }}
        className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]"
      >
        <div className="space-y-6">
          <Card className="relative overflow-hidden p-6">
            <div className="pointer-events-none absolute -top-24 -right-24 size-72 rounded-full bg-primary/20 blur-3xl" />
            <div className="relative">
              <div className="mb-4 inline-flex rounded-lg bg-muted p-1">
                {(
                  [
                    { v: "keyword", label: "Brand / keyword", icon: Type },
                    { v: "page_id", label: "Page ID", icon: Hash },
                  ] as const
                ).map(({ v, label, icon: Icon }) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => set("search_type", v)}
                    className={cn(
                      "inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-medium transition-all",
                      form.search_type === v ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    <Icon className="size-3.5" /> {label}
                  </button>
                ))}
              </div>
              <div className="relative">
                <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted-foreground" />
                <input
                  autoFocus
                  value={form.query}
                  onChange={(e) => set("query", e.target.value)}
                  placeholder={form.search_type === "page_id" ? "e.g. 129669023798560" : "e.g. Gymshark, Glossier, Huel…"}
                  className={cn(
                    "h-16 w-full rounded-xl border bg-background/50 pr-4 pl-12 text-xl font-medium tracking-tight outline-none transition-colors placeholder:font-normal placeholder:text-muted-foreground/60 focus:border-ring focus:ring-4 focus:ring-ring/15",
                    pageIdInvalid ? "border-destructive" : "border-input",
                  )}
                />
              </div>
              <p className={cn("mt-2 flex items-center gap-1.5 text-xs", pageIdInvalid ? "text-destructive" : "text-muted-foreground")}>
                <Info className="size-3.5" />
                {pageIdInvalid
                  ? "A Page ID contains digits only."
                  : form.search_type === "page_id"
                    ? "Most precise: scans only ads from this exact Facebook Page. Find it under “Page transparency” on the brand's Page or in any Ad Library result."
                    : "Keyword search matches ad text, so it can include resellers and affiliates — turn on “exact page match” to filter them out."}
              </p>
              <div className="mt-4 max-w-sm">
                <Label htmlFor="cname">Competitor display name (optional)</Label>
                <Input id="cname" className="mt-1.5" placeholder="Defaults to the brand / page name" value={form.competitor_name} onChange={(e) => set("competitor_name", e.target.value)} />
              </div>
            </div>
          </Card>

          <Card className="space-y-6 p-6">
            <div>
              <div className="mb-2.5 flex items-center gap-2 text-sm font-medium">
                <Globe2 className="size-4 text-muted-foreground" /> Country
              </div>
              <CountryPicker value={form.country} onChange={(v) => set("country", v)} />
            </div>
            <div>
              <div className="mb-2.5 text-sm font-medium">Platforms</div>
              <div className="flex flex-wrap gap-2">
                <Chip active={form.platforms.length === 0} onClick={() => set("platforms", [])}>
                  All platforms
                </Chip>
                {PLATFORMS.map((p) => (
                  <Chip
                    key={p.value}
                    active={form.platforms.includes(p.value)}
                    onClick={() => set("platforms", form.platforms.includes(p.value) ? form.platforms.filter((x) => x !== p.value) : [...form.platforms, p.value])}
                  >
                    <PlatformIcon platform={p.value} /> {p.label}
                  </Chip>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2.5 text-sm font-medium">Media type</div>
              <div className="flex flex-wrap gap-2">
                {MEDIA.map((m) => (
                  <Chip key={m.value} active={form.media_type === m.value} onClick={() => set("media_type", m.value)}>
                    {m.label}
                  </Chip>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2.5 text-sm font-medium">Ad status</div>
              <div className="flex flex-wrap gap-2">
                {STATUSES.map((s) => (
                  <Chip key={s.value} active={form.active_status === s.value} onClick={() => set("active_status", s.value)}>
                    {s.label}
                  </Chip>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-1 flex items-center justify-between text-sm font-medium">
                <span>Max ads</span>
                <span className="num rounded-md bg-muted px-2 py-0.5 text-xs">{form.max_ads}</span>
              </div>
              <Slider min={10} max={1000} step={10} value={[form.max_ads]} onValueChange={([v]) => set("max_ads", v)} />
              <div className="num flex justify-between text-[11px] text-muted-foreground">
                <span>10</span>
                <span>1000</span>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className={cn("flex items-start justify-between gap-3 rounded-lg border border-border p-3", form.search_type === "page_id" && "opacity-50")}>
                <span>
                  <span className="block text-sm font-medium">Exact page match</span>
                  <span className="block text-xs text-muted-foreground">Keep only pages whose name contains the keyword</span>
                </span>
                <Switch checked={form.exact_page} disabled={form.search_type === "page_id"} onCheckedChange={(v) => set("exact_page", v)} />
              </label>
              <label className="flex items-start justify-between gap-3 rounded-lg border border-border p-3">
                <span>
                  <span className="flex items-center gap-1.5 text-sm font-medium">
                    <Eye className="size-3.5" /> Visible browser
                  </span>
                  <span className="block text-xs text-muted-foreground">Watch Chrome work — handy for debugging</span>
                </span>
                <Switch checked={visible} onCheckedChange={setVisible} />
              </label>
            </div>
          </Card>
        </div>

        <div className="xl:sticky xl:top-24 xl:self-start">
          <motion.div initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }}>
            <Card className="p-5">
              <div className="text-sm font-semibold">Scan summary</div>
              <dl className="mt-4 space-y-2.5 text-sm">
                {[
                  ["Target", form.query.trim() || "—"],
                  ["Mode", form.search_type === "page_id" ? "Exact Page ID" : form.exact_page ? "Keyword · exact page" : "Keyword"],
                  ["Country", `${flag(form.country)} ${countryName(form.country)}`],
                  ["Platforms", form.platforms.length ? `${form.platforms.length} selected` : "All"],
                  ["Media", MEDIA.find((m) => m.value === form.media_type)?.label],
                  ["Max ads", form.max_ads],
                ].map(([k, v]) => (
                  <div key={k as string} className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">{k}</dt>
                    <dd className="truncate text-right font-medium">{v}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-2.5 text-xs text-muted-foreground">
                <Clock className="size-4 text-primary" />
                <span>
                  Estimated <span className="num font-semibold text-foreground">~{formatDuration(eta)}</span>
                  {stats.data?.avg_ads_per_minute ? " (from your past scans)" : ""}
                </span>
              </div>
              <Button type="submit" size="lg" className="mt-4 w-full" disabled={!canSubmit || start.isPending}>
                {start.isPending ? <Loader2 className="animate-spin" /> : <Radar />}
                Start scan
              </Button>
              {preview.data?.url && (
                <a href={preview.data.url} target="_blank" rel="noreferrer" className="mt-3 flex items-center justify-center gap-1.5 text-xs text-muted-foreground hover:text-primary">
                  Open this search in the Ad Library <ExternalLink className="size-3" />
                </a>
              )}
              <p className="mt-4 border-t border-border pt-3 text-[11px] leading-relaxed text-muted-foreground">
                Reads public pages only — no login, no captcha bypass. Scans are rate-limited and paced like a human browsing.
              </p>
            </Card>
          </motion.div>
        </div>
      </form>
    </>
  );
}
