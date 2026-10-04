import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import { Dialog as DialogPrimitive } from "radix-ui";
import { History, Moon, Radar, Search, Users } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { NAV } from "./nav";

const itemClass =
  "flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground data-[selected=true]:bg-accent data-[selected=true]:text-foreground [&_svg]:size-4";
const groupClass = "px-1 py-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground";

export function CommandPalette({ open, onOpenChange, onToggleTheme }: { open: boolean; onOpenChange: (o: boolean) => void; onToggleTheme: () => void }) {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const scans = useQuery({ queryKey: ["scans", "palette"], queryFn: () => api.scans({ limit: 8 }), enabled: open });
  const comps = useQuery({ queryKey: ["competitors"], queryFn: api.competitors, enabled: open });
  const go = (to: string) => {
    onOpenChange(false);
    setSearch("");
    navigate(to);
  };
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm" />
        <DialogPrimitive.Content className="fixed top-[18%] left-1/2 z-50 w-full max-w-xl -translate-x-1/2 overflow-hidden rounded-2xl border border-border bg-popover shadow-2xl outline-none">
          <DialogPrimitive.Title className="sr-only">Command palette</DialogPrimitive.Title>
          <Command loop>
            <div className="flex items-center gap-2 border-b border-border px-4">
              <Search className="size-4 text-muted-foreground" />
              <Command.Input
                value={search}
                onValueChange={setSearch}
                placeholder="Type a command or search ads…"
                className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
            </div>
            <Command.List className="max-h-96 overflow-y-auto p-1">
              <Command.Empty className="px-4 py-8 text-center text-sm text-muted-foreground">No matches.</Command.Empty>
              {search.trim().length > 1 && (
                <Command.Group heading="Search" className={groupClass}>
                  <Command.Item value={`search-ads ${search}`} onSelect={() => go(`/ads?q=${encodeURIComponent(search.trim())}`)} className={itemClass}>
                    <Search /> Search ads for “{search.trim()}”
                  </Command.Item>
                  <Command.Item value={`scan-brand ${search}`} onSelect={() => go(`/scan/new?q=${encodeURIComponent(search.trim())}`)} className={itemClass}>
                    <Radar /> Start a scan for “{search.trim()}”
                  </Command.Item>
                </Command.Group>
              )}
              <Command.Group heading="Navigate" className={groupClass}>
                {NAV.map(({ to, label, icon: Icon }) => (
                  <Command.Item key={to} value={label} onSelect={() => go(to)} className={itemClass}>
                    <Icon /> {label}
                  </Command.Item>
                ))}
              </Command.Group>
              {!!comps.data?.length && (
                <Command.Group heading="Competitors" className={groupClass}>
                  {comps.data.slice(0, 8).map((c) => (
                    <Command.Item key={c.id} value={`competitor ${c.name}`} onSelect={() => go(`/ads?competitor=${c.id}`)} className={itemClass}>
                      <Users /> {c.name} <span className="ml-auto text-xs">{c.ad_count} ads</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}
              {!!scans.data?.items.length && (
                <Command.Group heading="Recent scans" className={groupClass}>
                  {scans.data.items.map((s) => (
                    <Command.Item key={s.id} value={`scan ${s.id} ${s.query}`} onSelect={() => go(`/scans/${s.id}`)} className={itemClass}>
                      <History /> {s.query} <span className="ml-auto text-xs">#{s.id} · {s.status}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}
              <Command.Group heading="Actions" className={groupClass}>
                <Command.Item value="toggle theme dark light" onSelect={() => { onToggleTheme(); onOpenChange(false); }} className={itemClass}>
                  <Moon /> Toggle light / dark
                </Command.Item>
              </Command.Group>
            </Command.List>
          </Command>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
