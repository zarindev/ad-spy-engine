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
  useGlobalEvents();
  useHotkey("k", useCallback(() => setPaletteOpen((o) => !o), []));

  return (
    <div className="flex min-h-screen">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onSearch={() => setPaletteOpen(true)} theme={theme} onToggleTheme={toggle} />
        <main className="mx-auto w-full max-w-[1600px] flex-1 px-6 py-7">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} onToggleTheme={toggle} />
    </div>
  );
}
