import { Crosshair, Gift, Heart, Lightbulb, Megaphone, Quote, Target, Users } from "lucide-react";
import type { AdAnalysis } from "@/lib/api";
import { titleCase } from "@/lib/utils";

export const HOOK_LABELS: Record<string, string> = {
  question: "Question",
  bold_claim: "Bold claim",
  problem_agitate: "Problem → agitate",
  social_proof: "Social proof",
  curiosity: "Curiosity",
  offer: "Offer",
  story: "Story",
};

export function AnalysisCards({ analysis }: { analysis: AdAnalysis }) {
  const items = [
    { icon: Crosshair, label: "Angle", value: analysis.angle },
    { icon: Heart, label: "Emotion", value: analysis.emotion && titleCase(analysis.emotion) },
    { icon: Gift, label: "Offer", value: analysis.offer ?? "No explicit offer" },
    { icon: Megaphone, label: "CTA", value: analysis.cta },
    { icon: Users, label: "Audience", value: analysis.target_audience_guess },
    { icon: Target, label: "Summary", value: analysis.one_line_summary },
  ];
  return (
    <div className="rounded-xl border border-primary/30 bg-gradient-to-b from-primary/8 to-transparent p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">AI analysis</span>
        <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[11px] font-semibold text-primary">
          {HOOK_LABELS[analysis.hook_type] ?? analysis.hook_type} hook
        </span>
      </div>
      {analysis.hook_text && (
        <blockquote className="mb-3 flex gap-2 rounded-lg bg-card px-3 py-2 text-sm italic">
          <Quote className="mt-0.5 size-3.5 shrink-0 text-primary" /> {analysis.hook_text}
        </blockquote>
      )}
      <div className="grid gap-2 sm:grid-cols-2">
        {items.map(({ icon: Icon, label, value }) => (
          <div key={label} className="rounded-lg bg-card/70 px-3 py-2">
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground"><Icon className="size-3" /> {label}</div>
            <div className="mt-0.5 text-sm">{value ?? "—"}</div>
          </div>
        ))}
      </div>
      {analysis.what_to_steal && (
        <div className="mt-3 flex gap-2.5 rounded-lg border border-gold/30 bg-gold/8 px-3 py-2.5">
          <Lightbulb className="mt-0.5 size-4 shrink-0 text-gold" />
          <div>
            <div className="text-[11px] font-semibold tracking-wide text-gold uppercase">What to steal</div>
            <div className="text-sm">{analysis.what_to_steal}</div>
          </div>
        </div>
      )}
      <div className="mt-2 text-right text-[10px] text-muted-foreground">{analysis.model}</div>
    </div>
  );
}
