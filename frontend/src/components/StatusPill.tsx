import { Ban, CheckCircle2, CircleSlash, Clock, Loader2, ShieldAlert, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { ScanStatus } from "@/lib/api";

const META: Record<ScanStatus, { label: string; variant: "success" | "warning" | "destructive" | "muted" | "default"; icon: typeof Clock; spin?: boolean }> = {
  queued: { label: "Queued", variant: "muted", icon: Clock },
  running: { label: "Running", variant: "default", icon: Loader2, spin: true },
  completed: { label: "Completed", variant: "success", icon: CheckCircle2 },
  failed: { label: "Failed", variant: "destructive", icon: XCircle },
  blocked: { label: "Blocked", variant: "warning", icon: ShieldAlert },
  cancelled: { label: "Cancelled", variant: "muted", icon: Ban },
  interrupted: { label: "Interrupted", variant: "warning", icon: CircleSlash },
};

export function StatusPill({ status }: { status: ScanStatus }) {
  const m = META[status] ?? META.queued;
  const Icon = m.icon;
  return (
    <Badge variant={m.variant}>
      <Icon className={m.spin ? "animate-spin" : undefined} />
      {m.label}
    </Badge>
  );
}
