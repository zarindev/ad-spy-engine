import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Radar, Trophy, Users } from "lucide-react";
import { motion } from "motion/react";
import { Link } from "react-router-dom";
import { CompetitorAvatar } from "@/components/CompetitorAvatar";
import { EmptyState, ErrorState, PageHeader } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatNumber, timeAgo } from "@/lib/utils";

export default function Competitors() {
  const q = useQuery({ queryKey: ["competitors"], queryFn: api.competitors });
  const list = (q.data ?? []).filter((c) => c.ad_count > 0);
  return (
    <>
      <PageHeader
        title="Competitors"
        description="Every brand you've scanned, with how long their ads survive."
        actions={<Button asChild><Link to="/scan/new"><Radar /> Track a competitor</Link></Button>}
      />
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-44" />)}</div>
      ) : !list.length ? (
        <EmptyState icon={Users} title="No competitors yet" description="Scan a brand and it appears here with its ad count, average lifespan and last scan." action={<Button asChild><Link to="/scan/new">Start a scan</Link></Button>} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {list.map((c, i) => (
            <motion.div key={c.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
              <Link to={`/competitors/${c.id}`}>
                <Card className="group p-5 transition-all hover:-translate-y-0.5 hover:border-primary/40">
                  <div className="flex items-center gap-3">
                    <CompetitorAvatar name={c.name} src={c.logo_url} className="size-11 rounded-xl" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-semibold">{c.name}</div>
                      <div className="text-xs text-muted-foreground">Last scan {timeAgo(c.last_scan_at)}{c.page_id ? ` · Page ${c.page_id}` : ""}</div>
                    </div>
                    <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                  </div>
                  <div className="mt-5 grid grid-cols-3 gap-2">
                    <div><div className="num text-xl font-semibold">{formatNumber(c.ad_count)}</div><div className="text-[11px] text-muted-foreground">Ads · {c.active_ads} active</div></div>
                    <div><div className="num text-xl font-semibold">{c.avg_days_running}</div><div className="text-[11px] text-muted-foreground">Avg. lifespan (days)</div></div>
                    <div><div className="num flex items-center gap-1 text-xl font-semibold text-gold"><Trophy className="size-4" />{c.winners}</div><div className="text-[11px] text-muted-foreground">Winners</div></div>
                  </div>
                </Card>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </>
  );
}
