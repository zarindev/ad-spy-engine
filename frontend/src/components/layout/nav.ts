import { FileText, History, LayoutDashboard, LayoutGrid, Radar, Settings, Users } from "lucide-react";

export const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/scan/new", label: "New Scan", icon: Radar },
  { to: "/scans", label: "Scan History", icon: History },
  { to: "/ads", label: "Results Gallery", icon: LayoutGrid },
  { to: "/competitors", label: "Competitors", icon: Users },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;
