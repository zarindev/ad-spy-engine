import { useQuery } from "@tanstack/react-query";
import { Loader2, Moon, Search, Sun } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

function ScanStatusPill() {
  const { data = [] } = useQuery({ queryKey: ["active-scans"], queryFn: api.activeScans, refetchInterval: 15000 });
  const running = data.filter((s) => s.status === "running");
  const queued = data.length - running.length;
  if (!data.length) {
    return (
      <div className="flex h-8 items-center gap-2 rounded-full border border-border px-3 text-xs text-muted-foreground">
        <span className="size-1.5 rounded-full bg-success" /> Idle
      </div>
    );
  }
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="flex h-8 items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-3 text-xs font-medium text-foreground"
        >
          <Loader2 className="size-3.5 animate-spin text-primary" />
          {running.length ? `Scanning “${running[0].query}”` : "Waiting"}
          {queued > 0 && <span className="text-muted-foreground">+{queued} queued</span>}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">Active scans</div>
        {data.map((s) => (
          <Link key={s.id} to={`/scans/${s.id}`} className="flex items-center justify-between rounded-lg px-2 py-2 text-sm hover:bg-accent">
            <span className="truncate">{s.query}</span>
            <span className={cn("text-xs", s.status === "running" ? "text-primary" : "text-muted-foreground")}>{s.status}</span>
          </Link>
        ))}
      </PopoverContent>
    </Popover>
  );
}

export function Topbar({ onSearch, theme, onToggleTheme }: { onSearch: () => void; theme: string; onToggleTheme: () => void }) {
  const mac = typeof navigator !== "undefined" && /Mac/.test(navigator.platform);
  return (
    <header className="glass sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border px-6">
      <button
        type="button"
        onClick={onSearch}
        className="flex h-9 w-full max-w-md items-center gap-2 rounded-lg border border-border bg-background/40 px-3 text-sm text-muted-foreground transition-colors hover:border-primary/40"
      >
        <Search className="size-4" />
        <span className="flex-1 text-left">Search ads, scans, pages…</span>
        <kbd className="num rounded border border-border bg-muted px-1.5 text-[10px]">{mac ? "⌘" : "Ctrl"} K</kbd>
      </button>
      <div className="ml-auto flex items-center gap-2">
        <ScanStatusPill />
        <Button variant="ghost" size="icon" onClick={onToggleTheme} aria-label="Toggle theme">
          {theme === "dark" ? <Sun /> : <Moon />}
        </Button>
      </div>
    </header>
  );
}
