import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import App from "./App";
import "./styles/globals.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <App />
        <Toaster
          theme="system"
          position="bottom-right"
          toastOptions={{ classNames: { toast: "!bg-popover !border-border !text-foreground", description: "!text-muted-foreground" } }}
        />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
);
