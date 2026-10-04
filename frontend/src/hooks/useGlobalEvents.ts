import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { toast } from "sonner";

/** Global SSE stream: keeps the status pill and lists fresh, toasts when scans finish. */
export function useGlobalEvents() {
  const qc = useQueryClient();
  useEffect(() => {
    let es: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout>;
    const connect = () => {
      es = new EventSource("/api/events");
      es.addEventListener("status", (e) => {
        try {
          const ev = JSON.parse((e as MessageEvent).data);
          const status = ev.data.status as string;
          qc.invalidateQueries({ queryKey: ["active-scans"] });
          if (["completed", "failed", "blocked", "cancelled"].includes(status)) {
            qc.invalidateQueries({ queryKey: ["dashboard"] });
            qc.invalidateQueries({ queryKey: ["scans"] });
            qc.invalidateQueries({ queryKey: ["competitors"] });
            qc.invalidateQueries({ queryKey: ["scan", ev.scan_id] });
            const scan = ev.data.scan ?? {};
            const label = scan.query ? `“${scan.query}”` : `#${ev.scan_id}`;
            if (status === "completed") toast.success(`Scan ${label} finished`, { description: `${scan.ads_found ?? 0} ads collected · ${scan.new_ads ?? 0} new` });
            else if (status === "blocked") toast.warning(`Scan ${label} was blocked by Meta`, { description: scan.block_reason ?? undefined });
            else if (status === "failed") toast.error(`Scan ${label} failed`, { description: scan.error ?? undefined });
          } else if (status === "queued" || status === "running") {
            qc.invalidateQueries({ queryKey: ["scans"] });
          }
        } catch {
          /* ignore malformed */
        }
      });
      es.onerror = () => {
        es?.close();
        retry = setTimeout(connect, 4000);
      };
    };
    connect();
    return () => {
      clearTimeout(retry);
      es?.close();
    };
  }, [qc]);
}
