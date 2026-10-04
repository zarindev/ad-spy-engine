/** Typed client for the FastAPI backend. */

export type Badge = "winner" | "promising" | "testing";
export type ScanStatus =
  | "queued" | "running" | "completed" | "failed" | "blocked" | "cancelled" | "interrupted";

export interface Ad {
  id: number;
  library_id: string;
  competitor_id: number;
  page_name: string | null;
  page_id: string | null;
  page_profile_image: string | null;
  status: "active" | "inactive";
  start_date: string | null;
  end_date: string | null;
  days_running: number;
  platforms: string[];
  headline: string | null;
  ad_copy: string | null;
  cta_text: string | null;
  media_type: string;
  display_format: string | null;
  variation_count: number;
  score: number;
  badge: Badge;
  badge_label: string;
  screenshot_url: string | null;
  thumbnail_url: string | null;
  landing_url: string | null;
  library_url: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
}

export interface ScoreComponent { value: number; weight: number; points: number; max_points: number }
export interface ScoreBreakdown {
  score: number;
  badge: Badge;
  inputs: { days_running: number; variation_count: number; platform_count: number; is_active: boolean };
  components: Record<"longevity" | "variations" | "platforms" | "recency", ScoreComponent>;
  explanation: string[];
}

export interface AdDetail extends Ad {
  description: string | null;
  cta_type: string | null;
  media_urls: string[];
  media_files: string[];
  score_breakdown: ScoreBreakdown;
  source: string;
  collation_id: string | null;
  history: { scan_id: number; captured_at: string; status: string; variation_count: number; days_running: number; score: number }[];
}

export interface Scan {
  id: number;
  competitor_id: number;
  competitor_name: string | null;
  competitor_logo: string | null;
  query: string;
  search_type: "keyword" | "page_id";
  country: string;
  media_type: string;
  platforms: string[];
  active_status: string;
  max_ads: number;
  exact_page: boolean;
  headless: boolean;
  status: ScanStatus;
  total_results: number | null;
  ads_found: number;
  ads_processed: number;
  ads_failed: number;
  new_ads: number;
  error: string | null;
  block_reason: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  ads_per_minute: number | null;
}

export interface Competitor {
  id: number;
  name: string;
  page_id: string | null;
  logo_url: string | null;
  last_scan_at: string | null;
  ad_count: number;
  active_ads: number;
  avg_days_running: number;
  max_days_running: number;
  avg_score: number;
  winners: number;
}

export interface DashboardStats {
  kpis: { ads_tracked: number; active_ads: number; winners: number; new_this_week: number; competitors: number; active_scans: number };
  recent_scans: Scan[];
  ads_per_day: { date: string; count: number }[];
  formats: { name: string; count: number }[];
  badges: { name: Badge; count: number }[];
  avg_ads_per_minute: number | null;
  activity: { scan_id: number; competitor_id: number; competitor_name: string; status: ScanStatus; new_ads: number; ads_found: number; at: string }[];
}

export interface Report {
  id: number;
  title: string;
  kind: string;
  scan_id: number | null;
  competitor_ids: number[];
  options: { sections?: string[]; top_n?: number };
  html_url: string | null;
  pdf_url: string | null;
  status: "ready" | "failed";
  error: string | null;
  created_at: string | null;
}

export interface SettingsPayload {
  settings: {
    scraping: Record<string, unknown> & {
      driver: string; headless: boolean; delay_range: [number, number]; max_ads: number;
      min_seconds_between_scans: number; screenshots: boolean; download_media: boolean;
      download_videos: boolean; max_media_mb: number; max_media_per_ad: number; no_new_ads_attempts: number;
    };
    scoring: { weights: Record<string, number>; thresholds: { winner: number; promising: number }; longevity_full_days: number };
    reports: { agency_name: string; primary_color: string; accent_color: string; logo_path: string | null };
    ai: { model: string; batch_size: number };
  };
  integrations: { ai: { configured: boolean; model: string }; telegram: { configured: boolean }; email: { configured: boolean } };
  data_dir: string;
  undetected_available: boolean;
}

export interface Paged<T> { items: T[]; total: number }

export interface ScanCreate {
  query: string;
  search_type: "keyword" | "page_id";
  competitor_name?: string;
  country: string;
  media_type: string;
  platforms: string[];
  active_status: "active" | "inactive" | "all";
  max_ads: number;
  exact_page: boolean;
  headless?: boolean | null;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new ApiError(0, "Can't reach the Ad Spy Engine server. Is it running?");
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message);
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}

export interface AdQuery {
  scan_id?: number;
  competitor_id?: number;
  q?: string;
  badge?: Badge | "";
  media_type?: string;
  platform?: string;
  status?: string;
  sort?: "score" | "days" | "newest" | "variations" | "first_seen";
  limit?: number;
  offset?: number;
}

export const api = {
  dashboard: () => request<DashboardStats>("/api/stats/dashboard"),
  scans: (p: { limit?: number; offset?: number; competitor_id?: number; status?: string } = {}) =>
    request<Paged<Scan>>(`/api/scans${qs(p)}`),
  activeScans: () => request<Scan[]>("/api/scans/active"),
  scan: (id: number) => request<Scan>(`/api/scans/${id}`),
  startScan: (body: ScanCreate) => request<Scan>("/api/scans", { method: "POST", body: JSON.stringify(body) }),
  cancelScan: (id: number) => request<{ ok: boolean }>(`/api/scans/${id}/cancel`, { method: "POST" }),
  rerunScan: (id: number) => request<Scan>(`/api/scans/${id}/rerun`, { method: "POST" }),
  scanLog: (id: number) => request<string>(`/api/scans/${id}/log`),
  previewUrl: (p: Record<string, string>) => request<{ url: string }>(`/api/scans/preview-url${qs(p)}`),
  ads: (q: AdQuery) => request<Paged<Ad>>(`/api/ads${qs({ ...q })}`),
  ad: (id: number) => request<AdDetail>(`/api/ads/${id}`),
  competitors: () => request<Competitor[]>("/api/competitors"),
  reports: () => request<Report[]>("/api/reports"),
  createReport: (body: { scan_id: number; title?: string; sections: string[]; top_n: number; pdf: boolean }) =>
    request<Report>("/api/reports", { method: "POST", body: JSON.stringify(body) }),
  deleteReport: (id: number) => request<{ ok: boolean }>(`/api/reports/${id}`, { method: "DELETE" }),
  settings: () => request<SettingsPayload>("/api/settings"),
  updateSettings: (patch: Record<string, Record<string, unknown>>) =>
    request<SettingsPayload & { rescored: number }>("/api/settings", { method: "PUT", body: JSON.stringify(patch) }),
};

export const exportUrl = {
  scanCsv: (id: number) => `/api/scans/${id}/export.csv`,
  adsCsv: (q: AdQuery & { ids?: string }) => `/api/ads/export.csv${qs({ ...q, sort: undefined, limit: undefined, offset: undefined })}`,
};

export const FINISHED: ScanStatus[] = ["completed", "failed", "blocked", "cancelled", "interrupted"];
