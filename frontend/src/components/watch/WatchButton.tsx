import { useQuery } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { scheduleLabel } from "@/lib/utils";
import { ScheduleDialog } from "./ScheduleDialog";

export function WatchButton({ competitorId }: { competitorId: number }) {
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["watchlist"], queryFn: api.watchlist });
  const item = q.data?.find((w) => w.competitor_id === competitorId);
  if (item) {
    return (
      <Button variant="outline" asChild title={scheduleLabel(item)}>
        <Link to="/watchlist">{item.enabled ? <Eye /> : <EyeOff />} {item.enabled ? scheduleLabel(item) : "Watch paused"}</Link>
      </Button>
    );
  }
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}><Eye /> Watch</Button>
      <ScheduleDialog open={open} onOpenChange={setOpen} competitorId={competitorId} />
    </>
  );
}
