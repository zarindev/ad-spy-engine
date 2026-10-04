import { FlaskConical, TrendingUp, Trophy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Badge as BadgeKind } from "@/lib/api";
import { cn } from "@/lib/utils";

export const BADGE_META: Record<BadgeKind, { label: string; icon: typeof Trophy; color: string }> = {
  winner: { label: "Winner", icon: Trophy, color: "var(--gold)" },
  promising: { label: "Promising", icon: TrendingUp, color: "var(--success)" },
  testing: { label: "Testing", icon: FlaskConical, color: "var(--info)" },
};

export function ScoreBadge({ badge, className }: { badge: BadgeKind; className?: string }) {
  const meta = BADGE_META[badge] ?? BADGE_META.testing;
  const Icon = meta.icon;
  return (
    <Badge variant={badge} className={className}>
      <Icon />
      {meta.label}
    </Badge>
  );
}

/** Circular score gauge. */
export function ScoreRing({ score, badge, size = 44, stroke = 4, className }: { score: number; badge: BadgeKind; size?: number; stroke?: number; className?: string }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = BADGE_META[badge]?.color ?? "var(--info)";
  return (
    <div className={cn("relative grid shrink-0 place-items-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--muted)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - Math.min(score, 100) / 100)}
          style={{ transition: "stroke-dashoffset 600ms ease" }}
        />
      </svg>
      <span className="num absolute text-[13px] font-semibold" style={{ fontSize: size * 0.3 }}>
        {score}
      </span>
    </div>
  );
}
