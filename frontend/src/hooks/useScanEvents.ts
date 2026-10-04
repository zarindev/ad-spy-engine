import { useEffect, useRef, useState } from "react";
import type { Ad, ScanStatus } from "@/lib/api";

export interface ScanProgress {
  total: number | null;
  found: number;
  processed: number;
  failed: number;
  max_ads: number;
}

export interface LogLine {
  id: number;
  level: string;
  message: string;
  ts: number;
}

export interface ScanEventState {
  status: string | null;
  progress: ScanProgress | null;
  logs: LogLine[];
  liveAds: Ad[];
  blocked: { reason: string; suggestions: string[] } | null;
  connected: boolean;
  finished: boolean;
}

const TERMINAL: string[] = ["completed", "failed", "blocked", "cancelled", "interrupted"];

/** Subscribes to /api/scans/:id/events (Server-Sent Events) while the scan is live. */
export function useScanEvents(scanId: number | null, enabled: boolean): ScanEventState {
  const [state, setState] = useState<ScanEventState>({
    status: null, progress: null, logs: [], liveAds: [], blocked: null, connected: false, finished: false,
  });
  const seen = useRef(new Set<number>());

  useEffect(() => {
    if (!scanId || !enabled) return;
    seen.current = new Set();
    setState({ status: null, progress: null, logs: [], liveAds: [], blocked: null, connected: false, finished: false });
    const es = new EventSource(`/api/scans/${scanId}/events`);
    const parse = (e: MessageEvent) => {
      try {
        return JSON.parse(e.data);
      } catch {
        return null;
      }
    };
    es.onopen = () => setState((s) => ({ ...s, connected: true }));
    es.onerror = () => setState((s) => ({ ...s, connected: false }));
    es.addEventListener("status", (e) => {
      const ev = parse(e as MessageEvent);
      if (!ev) return;
      const status = ev.data.status as ScanStatus | string;
      const finished = TERMINAL.includes(status);
      setState((s) => ({ ...s, status, finished: s.finished || finished }));
      if (finished) es.close();
    });
    es.addEventListener("progress", (e) => {
      const ev = parse(e as MessageEvent);
      if (ev) setState((s) => ({ ...s, progress: ev.data }));
    });
    es.addEventListener("log", (e) => {
      const ev = parse(e as MessageEvent);
      if (!ev || seen.current.has(ev.id)) return;
      seen.current.add(ev.id);
      setState((s) => ({
        ...s,
        logs: [...s.logs, { id: ev.id, level: ev.data.level, message: ev.data.message, ts: ev.ts }].slice(-400),
      }));
    });
    es.addEventListener("ad", (e) => {
      const ev = parse(e as MessageEvent);
      if (!ev) return;
      const a = ev.data.ad;
      const ad = { ...a, screenshot_url: a.screenshot_path ? `/files/${a.screenshot_path}` : null } as Ad;
      setState((s) => ({ ...s, liveAds: [ad, ...s.liveAds.filter((x) => x.id !== ad.id)].slice(0, 300) }));
    });
    es.addEventListener("blocked", (e) => {
      const ev = parse(e as MessageEvent);
      if (ev) setState((s) => ({ ...s, blocked: ev.data }));
    });
    return () => es.close();
  }, [scanId, enabled]);

  return state;
}
