import { Tooltip } from "@/components/ui/tooltip";
import { cn, titleCase } from "@/lib/utils";

/** Simplified monochrome placement glyphs (drawn here, not brand assets). */
const PATHS: Record<string, React.ReactNode> = {
  FACEBOOK: <path d="M13.5 21v-7.2h2.4l.4-2.9h-2.8V9.1c0-.8.2-1.4 1.4-1.4h1.5V5.1c-.3 0-1.1-.1-2.2-.1-2.2 0-3.6 1.3-3.6 3.7v2.2H8.2v2.9h2.4V21" />,
  INSTAGRAM: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="4.5" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="12" cy="12" r="3.6" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="16.8" cy="7.2" r="1.1" />
    </>
  ),
  MESSENGER: (
    <path d="M12 3.5c-4.8 0-8.5 3.5-8.5 8.1 0 2.4 1 4.5 2.7 6v2.9l2.6-1.4c1 .3 2 .4 3.2.4 4.8 0 8.5-3.5 8.5-8.1S16.8 3.5 12 3.5Zm.9 10.8-2.2-2.3-4.2 2.3 4.6-4.9 2.2 2.3 4.2-2.3-4.6 4.9Z" />
  ),
  AUDIENCE_NETWORK: (
    <>
      <circle cx="12" cy="12" r="2.6" />
      <circle cx="12" cy="12" r="6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeDasharray="3 2.2" />
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.4" opacity=".55" />
    </>
  ),
  THREADS: (
    <path
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      d="M16.6 8.6C15.8 6.5 14.1 5 11.9 5 8.5 5 6.2 7.7 6.2 12s2.3 7 5.7 7c2.7 0 4.9-1.6 4.9-4 0-2.3-2.1-3.4-4.4-3.4-2 0-3.3 1-3.3 2.4 0 1.2 1 2 2.4 2 2.4 0 3.4-2.1 3.4-4.8"
    />
  ),
  WHATSAPP: (
    <path d="M12 3.5a8.4 8.4 0 0 0-7.3 12.6L3.5 20.5l4.5-1.2A8.4 8.4 0 1 0 12 3.5Zm4.2 11.6c-.2.5-1 1-1.5 1-.4.1-.9.1-1.5-.1-2.6-.9-4.3-3.4-4.4-3.6-.1-.2-1-1.4-1-2.6 0-1.2.7-1.8.9-2.1.2-.2.5-.3.6-.3h.5c.2 0 .4 0 .6.4l.8 1.9c.1.1.1.3 0 .5l-.3.4-.4.4c-.1.1-.3.3-.1.5.1.3.6 1 1.3 1.6.9.8 1.6 1 1.8 1.1.2.1.4.1.5-.1l.7-.9c.2-.2.3-.2.6-.1l1.8.9c.2.1.4.2.4.3.1.1.1.7-.1 1.2Z" />
  ),
};

export function PlatformIcon({ platform, className }: { platform: string; className?: string }) {
  const p = PATHS[platform.toUpperCase()];
  if (!p) return null;
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={cn("size-3.5", className)} aria-label={titleCase(platform)}>
      {p}
    </svg>
  );
}

export function PlatformIcons({ platforms, className, size }: { platforms: string[]; className?: string; size?: string }) {
  if (!platforms?.length) return <span className="text-xs text-muted-foreground">—</span>;
  return (
    <div className={cn("flex items-center gap-1.5 text-muted-foreground", className)}>
      {platforms.map((p) => (
        <Tooltip key={p} content={titleCase(p)}>
          <span className="inline-flex hover:text-foreground">
            <PlatformIcon platform={p} className={size} />
          </span>
        </Tooltip>
      ))}
    </div>
  );
}

export const ALL_PLATFORMS = ["FACEBOOK", "INSTAGRAM", "MESSENGER", "AUDIENCE_NETWORK", "THREADS", "WHATSAPP"];
