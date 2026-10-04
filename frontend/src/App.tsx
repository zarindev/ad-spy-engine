import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { Skeleton } from "@/components/ui/skeleton";

const Dashboard = lazy(() => import("@/pages/Dashboard"));
const NewScan = lazy(() => import("@/pages/NewScan"));
const LiveScan = lazy(() => import("@/pages/LiveScan"));
const Scans = lazy(() => import("@/pages/Scans"));
const Results = lazy(() => import("@/pages/Results"));
const Reports = lazy(() => import("@/pages/Reports"));
const Settings = lazy(() => import("@/pages/Settings"));
const NotFound = lazy(() => import("@/pages/NotFound"));

function PageFallback() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-9 w-64" />
      <Skeleton className="h-72" />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          {[
            ["/", Dashboard],
            ["/scan/new", NewScan],
            ["/scans", Scans],
            ["/scans/:id", LiveScan],
            ["/ads", Results],
            ["/reports", Reports],
            ["/settings", Settings],
            ["*", NotFound],
          ].map(([path, Page]) => {
            const C = Page as React.ComponentType;
            return (
              <Route
                key={path as string}
                path={path as string}
                element={
                  <Suspense fallback={<PageFallback />}>
                    <C />
                  </Suspense>
                }
              />
            );
          })}
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
