import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input, Label } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api, type WatchItem, type WatchSchedule } from "@/lib/api";
import { cn, WEEKDAYS } from "@/lib/utils";

const DEFAULT: WatchSchedule = { frequency: "daily", hour: 9, minute: 0, weekday: 0, notify: true };

/** Add a competitor to the watchlist (competitorId/picker) or edit an existing item. */
export function ScheduleDialog({
  open, onOpenChange, item, competitorId,
}: { open: boolean; onOpenChange: (o: boolean) => void; item?: WatchItem; competitorId?: number }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<WatchSchedule & { max_ads: number }>({ ...DEFAULT, max_ads: 200 });
  const [picked, setPicked] = useState<number | null>(competitorId ?? null);
  const competitors = useQuery({ queryKey: ["competitors"], queryFn: api.competitors, enabled: open && !item && !competitorId });
  const watched = useQuery({ queryKey: ["watchlist"], queryFn: api.watchlist, enabled: open && !item });

  useEffect(() => {
    if (!open) return;
    setPicked(competitorId ?? null);
    setForm(item ? { frequency: item.frequency, hour: item.hour, minute: item.minute, weekday: item.weekday, notify: item.notify, max_ads: item.max_ads } : { ...DEFAULT, max_ads: 200 });
  }, [open, item, competitorId]);

  const save = useMutation({
    mutationFn: () => (item ? api.watchUpdate(item.id, form) : api.watchAdd({ ...form, competitor_id: picked! })),
    onSuccess: (w) => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      toast.success(item ? "Schedule updated" : `Watching ${w.competitor_name}`, { description: "Runs while Ad Spy Engine is open." });
      onOpenChange(false);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't save"),
  });

  const watchedIds = new Set((watched.data ?? []).map((w) => w.competitor_id));
  const options = (competitors.data ?? []).filter((c) => c.ad_count > 0 && !watchedIds.has(c.id));
  const time = `${String(form.hour).padStart(2, "0")}:${String(form.minute).padStart(2, "0")}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <div className="mb-5 flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-primary/15 text-primary"><CalendarClock className="size-5" /></div>
          <div>
            <DialogTitle>{item ? `Schedule for ${item.competitor_name}` : "Watch a competitor"}</DialogTitle>
            <DialogDescription className="mt-0">Re-scan automatically and get alerted about new, stopped and scaled ads.</DialogDescription>
          </div>
        </div>
        <div className="space-y-4">
          {!item && !competitorId && (
            <div>
              <Label>Competitor</Label>
              {options.length ? (
                <div className="mt-1.5 flex max-h-40 flex-wrap gap-1.5 overflow-y-auto">
                  {options.map((c) => (
                    <button key={c.id} type="button" onClick={() => setPicked(c.id)} className={cn("h-8 rounded-full border px-3 text-xs font-medium", picked === c.id ? "border-primary/60 bg-primary/15" : "border-border text-muted-foreground hover:text-foreground")}>
                      {c.name}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="mt-1.5 text-sm text-muted-foreground">Every scanned competitor is already watched — run a scan for a new brand first.</p>
              )}
            </div>
          )}
          <div>
            <Label>Frequency</Label>
            <div className="mt-1.5 inline-flex rounded-lg bg-muted p-1">
              {(["daily", "weekly"] as const).map((f) => (
                <button key={f} type="button" onClick={() => setForm({ ...form, frequency: f })} className={cn("h-8 rounded-md px-4 text-xs font-medium capitalize", form.frequency === f ? "bg-card shadow-sm" : "text-muted-foreground")}>
                  {f}
                </button>
              ))}
            </div>
          </div>
          {form.frequency === "weekly" && (
            <div>
              <Label>Day</Label>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {WEEKDAYS.map((d, i) => (
                  <button key={d} type="button" onClick={() => setForm({ ...form, weekday: i })} className={cn("h-8 w-11 rounded-lg border text-xs font-medium", form.weekday === i ? "border-primary/60 bg-primary/15" : "border-border text-muted-foreground")}>
                    {d.slice(0, 3)}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="wtime">Time (your local time)</Label>
              <Input id="wtime" type="time" className="num mt-1.5" value={time} onChange={(e) => {
                const [h, m] = e.target.value.split(":").map(Number);
                if (!Number.isNaN(h)) setForm({ ...form, hour: h, minute: m || 0 });
              }} />
            </div>
            <div>
              <Label htmlFor="wmax">Max ads per scan</Label>
              <Input id="wmax" type="number" min={10} max={5000} className="num mt-1.5" value={form.max_ads} onChange={(e) => setForm({ ...form, max_ads: Number(e.target.value) })} />
            </div>
          </div>
          <label className="flex items-center justify-between rounded-lg border border-border p-3">
            <span>
              <span className="block text-sm font-medium">Send alerts</span>
              <span className="block text-xs text-muted-foreground">Telegram / email when something changes (configure in Settings)</span>
            </span>
            <Switch checked={form.notify} onCheckedChange={(v) => setForm({ ...form, notify: v })} />
          </label>
          <p className="text-xs text-muted-foreground">
            Tip: a max-ads limit above the competitor's ad count lets Ad Spy Engine reliably detect stopped ads.
          </p>
          <Button className="w-full" disabled={save.isPending || (!item && !picked)} onClick={() => save.mutate()}>
            {save.isPending && <Loader2 className="animate-spin" />} {item ? "Save schedule" : "Add to watchlist"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
