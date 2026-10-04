import type { LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatNumber } from "@/lib/utils";

export function KpiCard({
  label, value, icon: Icon, hint, tone = "primary", loading, index = 0,
}: { label: string; value: number | null | undefined; icon: LucideIcon; hint?: React.ReactNode; tone?: "primary" | "gold" | "success" | "info"; loading?: boolean; index?: number }) {
  const toneClass = { primary: "text-primary bg-primary/12", gold: "text-gold bg-gold/12", success: "text-success bg-success/12", info: "text-info bg-info/12" }[tone];
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }}>
      <Card className="relative overflow-hidden p-5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground">{label}</span>
          <span className={cn("grid size-8 place-items-center rounded-lg", toneClass)}>
            <Icon className="size-4" />
          </span>
        </div>
        {loading ? <Skeleton className="mt-3 h-8 w-20" /> : <div className="num mt-2 text-3xl font-semibold tracking-tight">{formatNumber(value)}</div>}
        {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      </Card>
    </motion.div>
  );
}
