import { Dialog as DialogPrimitive } from "radix-ui";
import { useCallback, useState } from "react";
import { Outlet } from "react-router-dom";
import { useGlobalEvents } from "@/hooks/useGlobalEvents";
import { useHotkey } from "@/hooks/useHotkey";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import { useTheme } from "@/hooks/useTheme";
import { CommandPalette } from "./CommandPalette";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell() {
  const { theme, toggle } = useTheme();
  const [collapsed, setCollapsed] = useLocalStorage("adspy-sidebar-collapsed", false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  useGlobalEvents();
  useHotkey("k", useCallback(() => setPaletteOpen((o) => !o), []));

  return (
    <div className="flex min-h-screen">
      <div className="hidden md:block">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      </div>
      <DialogPrimitive.Root open={menuOpen} onOpenChange={setMenuOpen}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px] md:hidden" />
          <DialogPrimitive.Content className="fixed inset-y-0 left-0 z-50 outline-none md:hidden" aria-describedby={undefined}>
            <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
            <Sidebar drawer collapsed={false} onNavigate={() => setMenuOpen(false)} />
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onSearch={() => setPaletteOpen(true)} onMenu={() => setMenuOpen(true)} theme={theme} onToggleTheme={toggle} />
        <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 md:px-6 md:py-7">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} onToggleTheme={toggle} />
    </div>
  );
}
