import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, CheckCircle2, KeyRound, Loader2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button, type ButtonProps } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { api, type AiScope } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

/** Opens a dialog: cost estimate first, explicit confirm, then live progress of the run. */
export function AiAnalyzeButton({ scope, label = "Analyze with AI", allowWinnersToggle, ...props }: { scope: AiScope; label?: string; allowWinnersToggle?: boolean } & ButtonProps) {
  const [open, setOpen] = useState(false);
  const [onlyWinners, setOnlyWinners] = useState(false);
  const [runId, setRunId] = useState<number | null>(null);
  const qc = useQueryClient();
  const fullScope = { ...scope, only_winners: onlyWinners };

  const estimate = useQuery({ queryKey: ["ai-estimate", fullScope], queryFn: () => api.aiEstimate(fullScope), enabled: open && !runId });
  const run = useQuery({
    queryKey: ["ai-run", runId],
    queryFn: () => api.aiRun(runId!),
    enabled: !!runId,
    refetchInterval: (q) => (q.state.data && ["completed", "failed"].includes(q.state.data.status) ? false : 1500),
  });
  const start = useMutation({
    mutationFn: () => api.aiStart(fullScope),
    onSuccess: (r) => setRunId(r.id),
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't start"),
  });

  const finished = !!run.data && ["completed", "failed"].includes(run.data.status);
  useEffect(() => {
    if (finished) {
      qc.invalidateQueries({ queryKey: ["ad"] });
      qc.invalidateQueries({ queryKey: ["competitor-profile"] });
    }
  }, [finished, qc]);

  const e = estimate.data;
  const r = run.data;
  const pct = r && r.total ? ((r.done + r.failed) / r.total) * 100 : 0;

  return (
    <>
      <Button variant="secondary" {...props} onClick={() => { setRunId(null); setOpen(true); }}>
        <Sparkles /> {label}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <div className="mb-4 flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-primary/15 text-primary"><BrainCircuit className="size-5" /></div>
            <div>
              <DialogTitle>AI copy analysis</DialogTitle>
              <DialogDescription className="mt-0">Hooks, angles, offers and what to steal — cached per ad.</DialogDescription>
            </div>
          </div>

          {estimate.isLoading && !runId && <Skeleton className="h-36" />}
          {estimate.isError && <p className="text-sm text-destructive">{(estimate.error as Error).message}</p>}

          {e && !e.enabled && !runId && (
            <div className="rounded-xl border border-border bg-muted/40 p-4 text-sm">
              <div className="flex items-center gap-2 font-medium"><KeyRound className="size-4 text-primary" /> AI analysis is off</div>
              <p className="mt-1 text-muted-foreground">
                Add <code className="num rounded bg-muted px-1">ANTHROPIC_API_KEY=…</code> to the <code className="num">.env</code> file in the project folder and restart the app.
                Estimated cost for this selection: <b className="text-foreground">${e.cost_usd.toFixed(2)}</b> ({e.to_analyze} ads).
              </p>
            </div>
          )}

          {e && e.enabled && !runId && (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2 text-center">
                {[["To analyze", formatNumber(e.to_analyze)], ["Already cached", formatNumber(e.cached)], ["Est. cost", `$${e.cost_usd.toFixed(2)}`]].map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-muted/50 px-2 py-3">
                    <div className="num text-lg font-semibold">{v}</div>
                    <div className="text-[11px] text-muted-foreground">{k}</div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                {e.model} · ~{formatNumber(e.input_tokens)} input + ~{formatNumber(e.output_tokens)} output tokens at ${e.pricing.input_per_mtok}/${e.pricing.output_per_mtok} per million. {e.note}
              </p>
              {allowWinnersToggle && (
                <label className="flex items-center justify-between rounded-lg border border-border p-3 text-sm">
                  Only analyze winners (score ≥ 75)
                  <Switch checked={onlyWinners} onCheckedChange={setOnlyWinners} />
                </label>
              )}
              <Button className="w-full" disabled={!e.to_analyze || start.isPending} onClick={() => start.mutate()}>
                {start.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}
                {e.to_analyze ? `Analyze ${e.to_analyze} ads · ~$${e.cost_usd.toFixed(2)}` : "Everything is already analyzed"}
              </Button>
            </div>
          )}

          {r && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 font-medium">
                  {finished ? <CheckCircle2 className="size-4 text-success" /> : <Loader2 className="size-4 animate-spin text-primary" />}
                  {r.status === "completed" ? "Analysis complete" : r.status === "failed" ? "Analysis failed" : "Analyzing…"}
                </span>
                <span className="num text-muted-foreground">{r.done + r.failed} / {r.total}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
              </div>
              <div className="num flex justify-between text-xs text-muted-foreground">
                <span>{r.done} done · {r.failed} failed · {r.cached} cached</span>
                <span>Actual cost ${r.cost_usd.toFixed(3)}</span>
              </div>
              {r.error && <p className="text-xs text-destructive">{r.error}</p>}
              {finished && <Button variant="outline" className="w-full" onClick={() => setOpen(false)}>Close</Button>}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
