import { useState } from "react";
import { cn } from "@/lib/utils";

export function CompetitorAvatar({ name, src, className }: { name: string | null; src?: string | null; className?: string }) {
  const [broken, setBroken] = useState(false);
  const initials = (name ?? "?").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return (
    <div className={cn("grid size-8 shrink-0 place-items-center overflow-hidden rounded-lg border border-border bg-gradient-to-br from-primary/30 to-primary/5 text-[11px] font-semibold", className)}>
      {src && !broken ? <img src={src} alt="" className="size-full object-cover" onError={() => setBroken(true)} /> : initials}
    </div>
  );
}
