import { cn, titleCase } from "@/lib/utils";

/** Labeled horizontal bars for one magnitude (single hue; values always printed). */
export function BarList({
  items, format = titleCase, className, max: maxItems = 8, labelWidth = "w-32", total: totalOverride,
}: { items: { name: string; count: number }[]; format?: (s: string) => string; className?: string; max?: number; labelWidth?: string; total?: number }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">No data yet.</p>;
  const shown = items.slice(0, maxItems);
  const top = Math.max(...shown.map((i) => i.count), 1);
  const total = totalOverride || items.reduce((a, b) => a + b.count, 0) || 1;
  return (
    <div className={cn("space-y-2", className)}>
      {shown.map((i) => (
        <div key={i.name} className="flex items-center gap-3 text-xs" title={`${i.count} (${((i.count / total) * 100).toFixed(0)}%)`}>
          <span className={cn("shrink-0 truncate", labelWidth)}>{format(i.name)}</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary" style={{ width: `${(i.count / top) * 100}%` }} />
          </div>
          <span className="num shrink-0 text-right whitespace-nowrap text-muted-foreground">
            {i.count} <span className="text-muted-foreground/60">· {((i.count / total) * 100).toFixed(0)}%</span>
          </span>
        </div>
      ))}
    </div>
  );
}
