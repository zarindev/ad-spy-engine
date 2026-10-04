import { ChevronsLeft, ChevronsRight } from "lucide-react";
import { NavLink } from "react-router-dom";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { LogoMark } from "./Logo";
import { NAV } from "./nav";

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <aside
      className={cn(
        "sticky top-0 flex h-screen shrink-0 flex-col border-r border-border bg-sidebar/80 backdrop-blur-xl transition-[width] duration-200",
        collapsed ? "w-[68px]" : "w-60",
      )}
    >
      <div className={cn("flex h-16 items-center gap-2.5 px-4", collapsed && "justify-center px-0")}>
        <LogoMark className="size-8 shrink-0" />
        {!collapsed && (
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-tight">Ad Spy Engine</div>
            <div className="text-[11px] text-muted-foreground">Meta Ad intelligence</div>
          </div>
        )}
      </div>
      <nav className="flex-1 space-y-0.5 px-3 py-2">
        {NAV.map(({ to, label, icon: Icon, ...rest }) => {
          const link = (
            <NavLink
              key={to}
              to={to}
              end={"end" in rest}
              className={({ isActive }) =>
                cn(
                  "relative flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                  isActive && "bg-primary/12 text-foreground",
                  collapsed && "justify-center px-0",
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute top-2 bottom-2 left-0 w-0.5 rounded-full bg-primary" />}
                  <Icon className={cn("size-[18px] shrink-0", isActive && "text-primary")} />
                  {!collapsed && label}
                </>
              )}
            </NavLink>
          );
          return collapsed ? (
            <Tooltip key={to} content={label} side="right">
              <span className="block">{link}</span>
            </Tooltip>
          ) : (
            link
          );
        })}
      </nav>
      <div className="p-3">
        <button
          type="button"
          onClick={onToggle}
          className={cn(
            "flex h-9 w-full items-center gap-3 rounded-lg px-2.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground",
            collapsed && "justify-center px-0",
          )}
        >
          {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
          {!collapsed && "Collapse"}
        </button>
      </div>
    </aside>
  );
}
